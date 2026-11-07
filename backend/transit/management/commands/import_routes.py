from django.core.management.base import BaseCommand

from transit.importer import import_routes


class Command(BaseCommand):
    help = "Upsert the real Nairobi routes, saccos, fares and stage coordinates. Safe to re-run."

    def handle(self, *args, **opts):
        r = import_routes()
        self.stdout.write(self.style.SUCCESS(
            f"{r['rows']} rows: {r['routes_created']} new routes, {r['saccos_created']} new saccos, {r['stages']} stages"
        ))
