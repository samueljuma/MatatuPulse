from django.test import TestCase

from transit.importer import import_routes
from transit.models import Route, RouteSacco, Stage


class ImportRoutesTests(TestCase):
    def test_import_is_complete_and_idempotent(self):
        r = import_routes()
        self.assertEqual(r["rows"], 97)
        self.assertEqual(Route.objects.count(), 97)
        self.assertEqual(RouteSacco.objects.count(), 97)
        self.assertEqual(Stage.objects.count(), 88)
        self.assertFalse(Stage.objects.filter(lat__isnull=True).exists())
        r = import_routes()
        self.assertEqual((r["routes_created"], r["saccos_created"]), (0, 0))

    def test_fares_and_lines(self):
        import_routes()
        route = Route.objects.get(line="A Line", number="100")
        self.assertEqual(route.name, "Nairobi CBD → Kiambu")
        sacco = route.saccos.get()
        self.assertEqual((sacco.sacco_name, sacco.sacco_code, sacco.usual_fare, sacco.fare_max), ("Super Metro", "SM", 80, 120))
        self.assertGreater(Route.objects.filter(number="23").count(), 1)  # same number on two lines
