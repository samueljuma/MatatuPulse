from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from reports.models import Alert, Event, Report
from reports.replay import seed_transit
from reports.services import (
    active_events,
    cast_vote,
    expire_stale,
    parse_sms,
    process_report,
    route_pill,
    sacco_fare,
)
from transit.models import Route, RouteSacco

User = get_user_model()


def sms(phone, text, at):
    r = Report(source="sms", sender_phone=phone, raw_text=text)
    return process_report(r, now=at, notify=False)


class Base(TestCase):
    def setUp(self):
        seed_transit()
        self.now = timezone.now()
        self.r100 = Route.objects.get(number="100", is_demo=True)
        self.flyers = RouteSacco.objects.get(sacco_name="Thika Road Flyers")

    def app(self, user, type_, at=None, **kw):
        r = Report(user=user, sender_phone=user.phone, source="app", type=type_, route=self.r100, **kw)
        return process_report(r, now=at or self.now, notify=False)


class ParseTests(Base):
    def test_fare_hike_with_stage_alias_and_sacco(self):
        p = parse_sms("100 bob odeon to g45 ni wizi, flyers")
        self.assertEqual(p.type, "fare_hike")
        self.assertEqual(p.stage.name, "Odeon")
        self.assertEqual(p.sacco, self.flyers)
        self.assertEqual(p.route, self.r100)
        self.assertEqual(p.fare, 100)

    def test_stage_alias_digits_are_not_a_fare(self):
        p = parse_sms("bei imepanda githurai 45 flyers")
        self.assertEqual(p.stage.name, "Githurai 45")
        self.assertIsNone(p.fare)

    def test_jam_prefers_destination_after_mpaka(self):
        p = parse_sms("imejam kutoka roysambu mpaka kasarani, kama 40 min")
        self.assertEqual(p.type, "jam")
        self.assertEqual(p.stage.name, "Kasarani")

    def test_accident_beats_closed(self):
        p = parse_sms("ACC NGARA msee ameangushwa, lane moja imefungwa")
        self.assertEqual((p.type, p.subtype), ("accident_police", "accident"))

    def test_police_subtype(self):
        p = parse_sms("karao wako stage githurai 45")
        self.assertEqual((p.type, p.subtype), ("accident_police", "police"))

    def test_closure_on_shared_stage_hits_both_routes(self):
        p = parse_sms("moi ave imefungwa")
        self.assertEqual(p.type, "route_closed")
        self.assertEqual(p.route.number, "23")
        self.assertEqual([r.number for r in p.extra_routes], ["46"])


class SpamTests(Base):
    def test_blocklist(self):
        r = sms("+254700000001", "WIN KES 50,000!! tuma 200 upate zawadi", self.now)
        self.assertTrue(r.is_spam)
        self.assertEqual(r.spam_reason, "blocklist")
        self.assertIsNone(r.event)

    def test_url_is_spam(self):
        self.assertEqual(sms("+254700000001", "fare odeon www.x.com", self.now).spam_reason, "blocklist")

    def test_unparseable(self):
        self.assertEqual(sms("+254700000001", "hi", self.now).spam_reason, "unparseable")

    def test_rate_limit_after_five_in_ten_minutes(self):
        for i in range(5):
            sms("+254700000009", "hello", self.now + timedelta(seconds=i))
        r = sms("+254700000009", "jam kasarani", self.now + timedelta(minutes=2))
        self.assertEqual(r.spam_reason, "rate_limit")
        # 11 minutes later the window has passed.
        r = sms("+254700000009", "jam kasarani", self.now + timedelta(minutes=12))
        self.assertFalse(r.is_spam)


class MergeVerifyTests(Base):
    def test_three_distinct_reporters_verify_and_alert(self):
        sms("+254700000001", "jam kasarani", self.now)
        sms("+254700000002", "imejam kasarani", self.now + timedelta(minutes=2))
        ev = Event.objects.get()
        self.assertEqual((ev.status, ev.reporter_count), ("pending", 2))
        sms("+254700000003", "tumekwama kasarani", self.now + timedelta(minutes=4))
        ev.refresh_from_db()
        self.assertEqual(ev.status, "verified")
        self.assertIsNotNone(ev.verified_at)
        self.assertEqual(Alert.objects.count(), 1)

    def test_same_phone_does_not_count_twice(self):
        for i in range(3):
            sms("+254700000001", "jam kasarani", self.now + timedelta(minutes=i))
        ev = Event.objects.get()
        self.assertEqual((ev.status, ev.reporter_count), ("pending", 1))

    def test_no_merge_after_30_minutes(self):
        sms("+254700000001", "jam kasarani", self.now)
        sms("+254700000002", "jam kasarani", self.now + timedelta(minutes=31))
        self.assertEqual(Event.objects.count(), 2)

    def test_different_stage_does_not_merge(self):
        sms("+254700000001", "jam kasarani", self.now)
        sms("+254700000002", "jam roysambu", self.now)
        self.assertEqual(Event.objects.count(), 2)

    def test_fare_hike_needs_same_sacco_and_fare_within_10(self):
        sms("+254700000001", "flyers fare 100 odeon", self.now)
        sms("+254700000002", "flyers fare 105 odeon", self.now)  # merges
        sms("+254700000003", "flyers fare 150 odeon", self.now)  # too far
        sms("+254700000004", "mwangaza fare 100 odeon", self.now)  # other sacco
        self.assertEqual(Event.objects.count(), 3)

    def test_app_report_merges_with_sms_and_returns_counts(self):
        sms("+254700000001", "zuri fare 90 odeon", self.now)
        sms("+254700000002", "zuri wameweka 90 bob", self.now)
        user = User.objects.create_user("+254711111111")
        zuri = RouteSacco.objects.get(sacco_name="Zuri Line")
        r = self.app(user, "fare_hike", sacco=zuri, fare=90, raw_text="fare ni 90 sasa")
        ev = r.event
        ev.refresh_from_db()
        self.assertEqual(ev.status, "verified")
        self.assertEqual(ev.reporter_count, 3)
        self.assertEqual(ev.previous_fare, 70)


class VoteExpiryTests(Base):
    def setUp(self):
        super().setUp()
        self.a = User.objects.create_user("+254711000001")
        self.b = User.objects.create_user("+254711000002")

    def test_still_accurate_counts_as_reporter_and_extends(self):
        sms("+254700000001", "jam kasarani", self.now)
        sms("+254700000002", "jam kasarani", self.now)
        ev = Event.objects.get()
        before = ev.expires_at
        ev = cast_vote(ev, self.a, "still", now=self.now + timedelta(minutes=20), notify=False)
        self.assertEqual(ev.status, "verified")
        self.assertGreater(ev.expires_at, before)

    def test_two_cleared_votes_clear(self):
        sms("+254700000001", "jam kasarani", self.now)
        ev = Event.objects.get()
        cast_vote(ev, self.a, "cleared", now=self.now, notify=False)
        ev = cast_vote(ev, self.b, "cleared", now=self.now, notify=False)
        self.assertEqual(ev.status, "cleared")

    def test_expiry_windows(self):
        sms("+254700000001", "jam kasarani", self.now)
        sms("+254700000002", "ajali ngara", self.now)
        sms("+254700000003", "moi ave imefungwa", self.now)
        expire_stale(self.now + timedelta(minutes=61))
        statuses = dict(Event.objects.values_list("type", "status"))
        self.assertEqual(statuses["jam"], "expired")
        self.assertEqual(statuses["accident_police"], "pending")
        expire_stale(self.now + timedelta(hours=3))
        statuses = dict(Event.objects.values_list("type", "status"))
        self.assertEqual(statuses["accident_police"], "expired")
        self.assertEqual(statuses["route_closed"], "pending")


class DerivedTests(Base):
    def test_sacco_fare_states(self):
        self.assertEqual(sacco_fare(self.flyers, self.now)["state"], "normal")
        sms("+254700000001", "flyers fare 100 odeon", self.now)
        f = sacco_fare(self.flyers, self.now)
        self.assertEqual((f["state"], f["fare"]), ("pending", 100))
        sms("+254700000002", "flyers fare 100 odeon", self.now)
        sms("+254700000003", "flyers fare 100 odeon", self.now)
        f = sacco_fare(self.flyers, self.now)
        self.assertEqual((f["state"], f["fare"], f["delta"]), ("up", 100, 30))

    def test_route_pill(self):
        self.assertEqual(route_pill(active_events(self.r100, self.now)), "maji_safi")
        sms("+254700000001", "jam kasarani", self.now)
        self.assertEqual(route_pill(active_events(self.r100, self.now)), "moderate")
        sms("+254700000002", "jam kasarani", self.now)
        sms("+254700000003", "jam kasarani", self.now)
        self.assertEqual(route_pill(active_events(self.r100, self.now)), "kwama")
