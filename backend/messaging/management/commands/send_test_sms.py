import json

from django.core.management.base import BaseCommand, CommandError

from accounts.models import normalize_phone
from messaging.providers import get_provider
from messaging.service import send_sms


class Command(BaseCommand):
    help = "Send one SMS through the configured provider and print the raw reply."

    def add_arguments(self, parser):
        parser.add_argument("phone")
        parser.add_argument("--text", default="MatatuPulse test: SMS is working.")

    def handle(self, phone, text, **opts):
        if not normalize_phone(phone):
            raise CommandError("Give a Kenyan number, e.g. 0712345678 or +254712345678")
        provider = get_provider()
        self.stdout.write(f"Provider: {provider.name}" + (f" -> {provider.url}" if hasattr(provider, "url") else ""))
        msg = send_sms(phone, text, kind="test", provider=provider)
        self.stdout.write(f"Status: {msg.status}  id: {msg.provider_message_id or '-'}  error: {msg.error or '-'}")
        self.stdout.write("Raw response: " + json.dumps(msg.response, indent=2, ensure_ascii=False))
        if msg.status != "sent":
            raise CommandError("Send failed")
