from django.test import override_settings
from rest_framework.test import APITestCase

from reports.replay import replay, seed_transit
from transit.importer import import_routes
from transit.models import Route, RouteSacco


TEST_NUMBERS = ["+254712345678", "+254798765432"]


@override_settings(OTP_TEST_NUMBERS=TEST_NUMBERS)
class ApiTests(APITestCase):
    def setUp(self):
        seed_transit()
        import_routes()
        replay()
        self.r100 = Route.objects.get(number="100", is_demo=True)

    def login(self, phone="0712345678"):
        r = self.client.post("/api/auth/otp/request", {"phone": phone}, format="json")
        self.assertEqual(r.status_code, 200)
        r = self.client.post("/api/auth/otp/verify", {"phone": phone, "code": "4729"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {r.data['access']}")
        return r.data

    def test_otp_rejects_bad_code(self):
        r = self.client.post("/api/auth/otp/verify", {"phone": "0712345678", "code": "0000"}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_routes_require_auth(self):
        self.assertEqual(self.client.get("/api/routes").status_code, 401)

    def test_route_list_and_search(self):
        self.login()
        r = self.client.get("/api/routes")
        self.assertEqual(len(r.data), 5 + 97)
        self.assertEqual([x["number"] for x in r.data[:5]], ["23", "46", "58", "111", "100"])  # demo first
        r = self.client.get("/api/routes", {"search": "g45"})
        self.assertEqual([x["number"] for x in r.data], ["100"])
        r = self.client.get("/api/routes", {"search": "flyers"})
        self.assertEqual([x["number"] for x in r.data], ["100"])

    def test_subscribe_toggle(self):
        self.login()
        url = f"/api/routes/{self.r100.id}/subscribe"
        self.assertTrue(self.client.post(url).data["subscribed"])
        self.assertTrue(self.client.get(f"/api/routes/{self.r100.id}").data["subscribed"])
        self.assertFalse(self.client.post(url).data["subscribed"])

    def test_demo_report_verifies_zuri_fare(self):
        self.login("0798765432")
        zuri = RouteSacco.objects.get(sacco_name="Zuri Line")
        r = self.client.post(
            "/api/reports",
            {"route": self.r100.id, "type": "fare_hike", "sacco": zuri.id, "fare": 90, "note": "fare ni 90 sasa Odeon"},
            format="json",
        )
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data["others_count"], 2)
        self.assertEqual(r.data["merged_count"], 2)
        self.assertTrue(r.data["verified_now"])
        self.assertEqual(r.data["event"]["status"], "verified")
        detail = self.client.get(f"/api/routes/{self.r100.id}").data
        zuri_card = next(s for s in detail["saccos"] if s["name"] == "Zuri Line")
        self.assertEqual((zuri_card["fare"], zuri_card["state"]), (90, "up"))

    def test_vote(self):
        self.login()
        detail = self.client.get(f"/api/routes/{self.r100.id}").data
        police = next(e for e in detail["events"] if e["label"] == "Police check")
        self.assertEqual(police["confirmations"], 2)
        r = self.client.post(f"/api/events/{police['id']}/vote", {"kind": "still"}, format="json")
        self.assertEqual(r.data["status"], "verified")
        self.assertEqual(r.data["my_vote"], "still")

    def test_sms_inbound_and_signal(self):
        self.assertEqual(
            self.client.post("/api/sms/inbound", {"from": "+254733000111", "text": "jam pangani"}).status_code, 403
        )
        r = self.client.post("/api/sms/inbound?token=test-webhook-token", {"msisdn": "254733000111", "message": "jam pangani"})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.data["spam"])
        s = self.client.get("/api/signal").data
        self.assertEqual(s["funnel"]["raw"], 201)
        self.assertEqual(s["reports"][0]["text"], "jam pangani")
        self.assertEqual(s["reports"][0]["phone"], "07•• ••• 111")

    def test_replay_staff_only(self):
        self.login()  # +254712345678 is not staff in tests (seed_demo makes it staff)
        self.assertEqual(self.client.post("/api/demo/replay").status_code, 403)
