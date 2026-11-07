"""Login codes: generate, hash, send by SMS, verify. Rules live in settings.OTP_*."""

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from messaging.service import send_sms

from .models import OtpCode


def hash_code(phone, code):
    return hmac.new(settings.SECRET_KEY.encode(), f"{phone}:{code}".encode(), hashlib.sha256).hexdigest()


def is_test_number(phone):
    return phone in settings.OTP_TEST_NUMBERS


@dataclass
class OtpRequestResult:
    ok: bool
    status: int = 200
    detail: str = ""
    retry_after: int = 0
    demo: bool = False


def request_code(phone, now=None):
    now = now or timezone.now()
    if is_test_number(phone):
        return OtpRequestResult(ok=True, demo=True)

    last = OtpCode.objects.filter(phone=phone).order_by("-created_at").first()
    if last:
        wait = settings.OTP_RESEND_SECONDS - int((now - last.created_at).total_seconds())
        if wait > 0:
            return OtpRequestResult(False, 429, f"Wait {wait} s before asking for another code.", retry_after=wait)
    hour_count = OtpCode.objects.filter(phone=phone, created_at__gte=now - timedelta(hours=1)).count()
    if hour_count >= settings.OTP_MAX_PER_HOUR:
        oldest = (
            OtpCode.objects.filter(phone=phone, created_at__gte=now - timedelta(hours=1))
            .order_by("created_at").first()
        )
        wait = max(60, int((oldest.created_at + timedelta(hours=1) - now).total_seconds()))
        return OtpRequestResult(False, 429, "Too many codes requested. Try again later.", retry_after=wait)

    code = f"{secrets.randbelow(10000):04d}"
    with transaction.atomic():
        OtpCode.objects.filter(phone=phone, used=False).update(used=True)  # older codes stop working
        otp = OtpCode.objects.create(
            phone=phone,
            code_hash=hash_code(phone, code),
            expires_at=now + timedelta(seconds=settings.OTP_TTL_SECONDS),
        )
    minutes = max(1, settings.OTP_TTL_SECONDS // 60)
    msg = send_sms(phone, f"Your MatatuPulse code is {code}. It expires in {minutes} minutes. Don't share it.", kind="otp")
    if msg.status != "sent":
        otp.delete()  # don't count a code the user never got
        return OtpRequestResult(False, 503, "We couldn't send the SMS right now. Please try again.")
    return OtpRequestResult(ok=True)


def verify_code(phone, code, now=None):
    """Returns True when the code is right. Burns the code after OTP_MAX_ATTEMPTS wrong tries."""
    now = now or timezone.now()
    if is_test_number(phone):
        return hmac.compare_digest(code, settings.DEMO_OTP)
    with transaction.atomic():
        otp = (
            OtpCode.objects.select_for_update()
            .filter(phone=phone, used=False, expires_at__gt=now)
            .order_by("-created_at")
            .first()
        )
        if not otp:
            return False
        if hmac.compare_digest(otp.code_hash, hash_code(phone, code)):
            otp.used = True
            otp.save(update_fields=["used"])
            return True
        otp.attempts += 1
        if otp.attempts >= settings.OTP_MAX_ATTEMPTS:
            otp.used = True
        otp.save(update_fields=["attempts", "used"])
        return False
