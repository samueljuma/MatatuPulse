from django.core.management.base import BaseCommand

from reports.replay import replay


class Command(BaseCommand):
    help = "Wipe reports/events and replay the 200 seed SMS relative to now."

    def handle(self, *args, **opts):
        counts = replay()
        self.stdout.write(self.style.SUCCESS(
            "Replayed: {raw} raw -> {spam} spam -> {events} events -> {verified} verified".format(**counts)
        ))
