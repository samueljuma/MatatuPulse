"""SMS providers. Pick one with SMS_PROVIDER=console|thrivewave.

ThriveWaveProvider is ported from Mat3Route's backend/app/providers/thrivewave.py.
The endpoint, path and sender are settings, so if ThriveWave's docs differ from
these defaults it is a config change, not a code change.
"""

import json
import logging
import socket
import urllib.error
import urllib.request
from dataclasses import dataclass, field

from django.conf import settings

log = logging.getLogger("matatupulse")

ID_KEYS = ("id", "message_id", "messageId", "sms_id", "transaction_id", "notification_id")
OK_STATUSES = {"200", "201", "success", "ok", "sent", "queued", "accepted"}


@dataclass
class SendResult:
    success: bool
    provider_message_id: str = ""
    error: str = ""
    response: dict | list | str | None = field(default=None)


class ConsoleProvider:
    """Development provider: logs the SMS instead of sending it."""

    name = "console"

    def send(self, to, text):
        log.info("[sms:console] to=%s text=%s", to, text)
        return SendResult(success=True, provider_message_id="", response={"console": True})


class ThriveWaveProvider:
    """ThriveVas SMS API: POST {base}{path}, x-api-key header, JSON {message, msisdn, sender_id}."""

    name = "thrivewave"

    def __init__(self, api_key=None, base_url=None, path=None, sender_id=None, callback_url=None, timeout=None):
        self.api_key = api_key if api_key is not None else settings.THRIVEWAVE_API_KEY
        self.base_url = (base_url or settings.THRIVEWAVE_BASE_URL).rstrip("/")
        self.path = path or settings.THRIVEWAVE_SMS_PATH
        self.sender_id = sender_id if sender_id is not None else settings.THRIVEWAVE_SENDER_ID
        self.callback_url = callback_url if callback_url is not None else settings.THRIVEWAVE_CALLBACK_URL
        self.timeout = timeout or settings.THRIVEWAVE_TIMEOUT_SECONDS

    @property
    def url(self):
        return self.base_url + self.path

    def build_request(self, to, text):
        payload = {"message": text, "msisdn": to.lstrip("+"), "sender_id": self.sender_id}
        if self.callback_url:
            payload["callback_url"] = self.callback_url
        return urllib.request.Request(
            self.url,
            data=json.dumps(payload).encode(),
            method="POST",
            headers={
                "x-api-key": self.api_key,
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "MatatuPulse/1.0",
            },
        )

    def send(self, to, text):
        if not self.api_key:
            return SendResult(success=False, error="THRIVEWAVE_API_KEY is not set")
        last_error = ""
        for attempt in (1, 2):  # one retry, on network errors only
            try:
                with urllib.request.urlopen(self.build_request(to, text), timeout=self.timeout) as resp:
                    return self.parse(resp.read())
            except urllib.error.HTTPError as exc:
                body = exc.read()
                parsed = _json_or_text(body)
                return SendResult(success=False, error=f"HTTP {exc.code}: {_message(parsed) or exc.reason}", response=parsed)
            except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError) as exc:
                last_error = f"network error: {getattr(exc, 'reason', exc)}"
                log.warning("[sms:thrivewave] attempt %s failed: %s", attempt, last_error)
        return SendResult(success=False, error=last_error)

    @staticmethod
    def parse(body):
        data = _json_or_text(body)
        if not isinstance(data, dict):
            return SendResult(success=True, response=data)
        status = data.get("status", data.get("code"))
        if status is not None and str(status).lower() not in OK_STATUSES:
            return SendResult(success=False, error=_message(data) or f"ThriveWave status {status}", response=data)
        if data.get("success") is False or data.get("error"):
            return SendResult(success=False, error=_message(data) or "ThriveWave reported an error", response=data)
        return SendResult(success=True, provider_message_id=extract_message_id(data), response=data)


def extract_message_id(data):
    for container in (data.get("data"), data):
        if isinstance(container, dict):
            for key in ID_KEYS:
                if container.get(key) not in (None, ""):
                    return str(container[key])
            for list_key in ("sms_ids", "message_ids", "messages"):
                items = container.get(list_key)
                if isinstance(items, list) and items:
                    first = items[0]
                    if isinstance(first, dict):
                        for key in ID_KEYS:
                            if first.get(key) not in (None, ""):
                                return str(first[key])
                    else:
                        return str(first)
        elif isinstance(container, list) and container and isinstance(container[0], dict):
            return extract_message_id(container[0])
    return ""


def _json_or_text(body):
    if not body:
        return {}
    try:
        return json.loads(body)
    except (ValueError, TypeError):
        return body.decode(errors="replace")[:500] if isinstance(body, bytes) else str(body)[:500]


def _message(data):
    if isinstance(data, dict):
        for key in ("message", "error", "detail", "description"):
            if data.get(key):
                return str(data[key])
    if isinstance(data, str):
        return data[:200]
    return ""


def get_provider():
    name = (settings.SMS_PROVIDER or "console").lower()
    if name == "thrivewave":
        return ThriveWaveProvider()
    return ConsoleProvider()
