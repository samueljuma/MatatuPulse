"""Seed the demo world and replay the 200 SMS through process_report."""

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from transit.models import Route, RouteSacco, RouteStage, Stage

from .fixtures import demo_data
from .models import Alert, Event, Report, Vote
from .services import cast_vote, expire_stale, process_report

User = get_user_model()

VOTER_PHONES = ["+254700000101", "+254700000102"]


@transaction.atomic
def seed_transit():
    stages = {}
    for name, aliases in demo_data.STAGE_ALIASES.items():
        defaults = {"aliases": aliases}
        if name in demo_data.STAGE_COORDS:
            defaults["lat"], defaults["lon"] = demo_data.STAGE_COORDS[name]
        stage, _ = Stage.objects.update_or_create(name=name, defaults=defaults)
        stages[name] = stage
    for number, name, via, stage_names in demo_data.ROUTES:
        route, _ = Route.objects.update_or_create(
            line="", number=number, name=name, defaults={"via": via, "is_demo": True}
        )
        RouteStage.objects.filter(route=route).delete()
        for i, s in enumerate(stage_names):
            RouteStage.objects.create(route=route, stage=stages[s], order=i)
        for sacco_name, fare in demo_data.SACCOS.get(number, []):
            RouteSacco.objects.update_or_create(
                route=route, sacco_name=sacco_name, defaults={"usual_fare": fare}
            )


@transaction.atomic
def replay(now=None):
    """Wipe reports/events and replay the seed SMS. Returns funnel counts."""
    now = now or timezone.now()
    Alert.objects.all().delete()
    Vote.objects.all().delete()
    Report.objects.all().delete()
    Event.objects.all().delete()

    messages, clearing_votes = demo_data.build_demo_sms(now)
    events_by_key = {}
    for m in messages:
        report = Report(source="sms", sender_phone=m["phone"], raw_text=m["text"], created_at=m["at"])
        process_report(report, now=m["at"], notify=False)
        if report.event_id and not m["key"].startswith("spam:"):
            events_by_key.setdefault(m["key"], report.event_id)

    voters = [User.objects.get_or_create(phone=p)[0] for p in VOTER_PHONES]
    seen = {}
    for key, at in clearing_votes:
        idx = seen.get(key, 0)
        seen[key] = idx + 1
        event = Event.objects.get(pk=events_by_key[key])
        cast_vote(event, voters[idx % len(voters)], "cleared", now=at, notify=False)

    expire_stale(now)
    return funnel()


def funnel():
    return {
        "raw": Report.objects.count(),
        "spam": Report.objects.filter(is_spam=True).count(),
        "events": Event.objects.count(),
        "verified": Event.objects.filter(verified_at__isnull=False).count(),
    }
