from django.test import TestCase
from django.utils import timezone

from reports.presenters import route_detail, route_summary
from reports.replay import replay, seed_transit
from reports.services import active_events
from transit.importer import import_routes
from transit.models import Route


class SeedFunnelTests(TestCase):
    def setUp(self):
        seed_transit()
        import_routes()  # production has the real catalogue loaded too
        self.now = timezone.now()
        self.counts = replay(self.now)

    def test_funnel_is_200_61_27_12(self):
        self.assertEqual(self.counts, {"raw": 200, "spam": 61, "events": 27, "verified": 12})

    def test_route_pills_match_designs(self):
        pills = {
            r.number: route_summary(r, None, self.now, active_events(r, self.now))["pill"]
            for r in Route.objects.filter(is_demo=True)
        }
        self.assertEqual(pills, {"23": "moderate", "46": "maji_safi", "58": "maji_safi", "111": "moderate", "100": "kwama"})

    def test_route_100_demo_state(self):
        d = route_detail(Route.objects.get(number="100", is_demo=True), None, self.now)
        self.assertEqual(d["banner"]["title"], "Accident at Ngara")
        self.assertEqual(d["banner"]["reports"], 5)
        fares = {s["name"]: (s["fare"], s["state"]) for s in d["saccos"]}
        self.assertEqual(fares["Thika Road Flyers"], (100, "up"))
        self.assertEqual(fares["Mwangaza Sacco"], (120, "up"))
        self.assertEqual(fares["Haraka Shuttle"], (70, "normal"))
        self.assertEqual(fares["Zuri Line"], (90, "pending"))
        self.assertEqual(d["alert_count"], 1)
