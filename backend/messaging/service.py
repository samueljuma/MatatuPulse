"""send_sms: the one way the app sends a text. Logs every attempt in OutboundSms and never raises."""

import logging

from django.utils import timezone

from accounts.models import normalize_phone

from .models import OutboundSms
from .providers import get_provider

log = logging.getLogger("matatupulse")


def send_sms(to, text, kind="alert", provider=None):
    provider = provider or get_provider()
    phone = normalize_phone(to) or str(to)
    msg = OutboundSms.objects.create(to=phone, text=text, kind=kind, provider=provider.name)
    try:
        result = provider.send(phone, text)
    except Exception as exc:  # a provider bug must never break a report or a login
        log.exception("[sms] provider crashed")
        msg.status, msg.error, msg.attempts = "failed", f"provider crashed: {exc}", 1
        msg.save(update_fields=["status", "error", "attempts"])
        return msg
    msg.attempts = 1
    msg.response = result.response if isinstance(result.response, (dict, list)) else (
        {"raw": result.response} if result.response else None
    )
    if result.success:
        msg.status = "sent"
        msg.sent_at = timezone.now()
        msg.provider_message_id = result.provider_message_id or ""
    else:
        msg.status = "failed"
        msg.error = result.error
        log.warning("[sms] %s to %s failed: %s", kind, phone, result.error)
    msg.save()
    return msg


DELIVERED = {"delivered", "delivrd", "success", "deliveredtoterminal", "1"}
UNDELIVERED = {"failed", "undelivered", "undeliv", "rejected", "expired", "deliveryimpossible", "0"}


def apply_delivery_report(data):
    """Update an OutboundSms from a DLR payload. Returns the row or None."""
    msg_id = next((str(data[k]) for k in ("id", "message_id", "messageId", "transaction_id", "sms_id") if data.get(k)), "")
    status = next((str(data[k]) for k in ("status", "delivery_status", "deliveryStatus", "dlr_status") if data.get(k)), "")
    if not msg_id:
        return None
    msg = OutboundSms.objects.filter(provider_message_id=msg_id).first()
    if not msg:
        return None
    s = status.replace(" ", "").replace("_", "").lower()
    if s in DELIVERED:
        msg.status, msg.delivered_at = "delivered", timezone.now()
    elif s in UNDELIVERED:
        msg.status = "undelivered"
        msg.error = status
    resp = msg.response if isinstance(msg.response, dict) else {}
    resp["dlr"] = data
    msg.response = resp
    msg.save()
    return msg
