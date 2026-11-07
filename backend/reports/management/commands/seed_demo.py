import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from reports.replay import replay, seed_transit
from transit.importer import import_routes


class Command(BaseCommand):
    help = "Seed demo routes, import the real route catalogue, create the staff user, and replay the 200 seed SMS."

    def add_arguments(self, parser):
        parser.add_argument("--no-replay", action="store_true", help="Only seed routes and saccos.")

    def handle(self, *args, **opts):
        seed_transit()  # demo routes first: SMS stage matching prefers the lowest route id
        r = import_routes()
        self.stdout.write(f"Imported {r['rows']} real route/sacco rows ({r['stages']} stages).")
        staff_phone = os.environ.get("DEMO_STAFF_PHONE", "+254712345678")
        User = get_user_model()
        user, _ = User.objects.get_or_create(phone=staff_phone)
        if not user.is_staff:
            user.is_staff = True
            user.save(update_fields=["is_staff"])
        self.stdout.write(f"Staff user: {staff_phone} (add it to OTP_TEST_NUMBERS to log in with 4729)")
        if not opts["no_replay"]:
            counts = replay()
            self.stdout.write(self.style.SUCCESS(
                "Replayed: {raw} raw -> {spam} spam -> {events} events -> {verified} verified".format(**counts)
            ))
