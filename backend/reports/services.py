"""process_report: the one function every app report and inbound SMS goes through.

parse (SMS only) -> spam check -> merge into an open Event -> verify at 3 distinct reporters.
Votes, expiry and the derived fare / route pill also live here.
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from transit.models import Route, RouteSacco, Stage

from . import keywords as kw
from .models import Alert, Event, EventType, Report, Vote
from .sms import send_sms

log = logging.getLogger("matatupulse")

VERIFY_AT = 3
CLEAR_AT = 2
MERGE_WINDOW = timedelta(minutes=30)
FARE_TOLERANCE = 10

TTL = {
    "jam": timedelta(minutes=60),
    "police": timedelta(minutes=60),
    "accident": timedelta(hours=2),
    "fare_hike": timedelta(hours=6),
    "route_closed": None,  # until cleared
}

OPEN_STATUSES = ("pending", "verified")


def ttl_for(type_, subtype=""):
    if type_ == EventType.ACCIDENT_POLICE:
        return TTL["police"] if subtype == "police" else TTL["accident"]
    return TTL.get(type_)


# --------------------------------------------------------------------------- parse

@dataclass
class Parsed:
    type: str = ""
    subtype: str = ""
    stage: Stage | None = None
    sacco: RouteSacco | None = None
    route: Route | None = None
    fare: int | None = None
    extra_routes: list = field(default_factory=list)


def _norm(text):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s]", " ", (text or "").lower())).strip()


def _has(norm, word):
    return re.search(rf"(?<![a-z0-9]){re.escape(word)}(?![a-z0-9])", norm) is not None


def parse_type(norm):
    for type_, words in kw.TYPE_KEYWORDS:
        if any(_has(norm, w) for w in words):
            subtype = ""
            if type_ == EventType.ACCIDENT_POLICE:
                subtype = "police" if any(_has(norm, w) for w in kw.POLICE_WORDS) else "accident"
            return type_, subtype
    return "", ""


def find_stage(norm):
    """Return (stage, matched_spans). Prefers the stage after 'mpaka'/'hadi' if present."""
    hits = []  # (position, stage, span)
    for stage in Stage.objects.all():
        for alias in [stage.name.lower(), *stage.aliases]:
            for m in re.finditer(rf"(?<![a-z0-9]){re.escape(_norm(alias))}(?![a-z0-9])", norm):
                hits.append((m.start(), stage, m.span()))
    if not hits:
        return None, []
    hits.sort(key=lambda h: (h[0], -(h[2][1] - h[2][0])))
    spans = [h[2] for h in hits]
    marker_pos = min(
        (m.start() for w in kw.DESTINATION_MARKERS for m in re.finditer(rf"\b{w}\b", norm)),
        default=None,
    )
    if marker_pos is not None:
        after = [h for h in hits if h[0] > marker_pos]
        if after:
            return after[0][1], spans
    return hits[0][1], spans


def find_sacco_name(norm):
    for name, aliases in kw.SACCO_ALIASES.items():
        if any(_has(norm, a) for a in aliases):
            return name
    return None


def find_fare(norm, skip_spans):
    masked = list(norm)
    for a, b in skip_spans:
        for i in range(a, b):
            masked[i] = " "
    m = re.search(r"(?<![0-9])(\d{2,3})(?![0-9])", "".join(masked))
    return int(m.group(1)) if m else None


def parse_sms(text):
    norm = _norm(text)
    p = Parsed()
    p.type, p.subtype = parse_type(norm)
    p.stage, spans = find_stage(norm)
    sacco_name = find_sacco_name(norm)

    # Resolve route: sacco wins (it belongs to exactly one route), else a route through the stage.
    if sacco_name:
        candidates = RouteSacco.objects.filter(sacco_name=sacco_name).select_related("route")
        if p.stage:
            on_stage = [s for s in candidates if s.route.stages.filter(pk=p.stage.pk).exists()]
            candidates = on_stage or list(candidates)
        p.sacco = candidates[0] if candidates else None
        if p.sacco:
            p.route = p.sacco.route
    if p.route is None and p.stage is not None:
        routes = list(p.stage.routes.order_by("id"))
        if routes:
            p.route = routes[0]
            if p.type == EventType.ROUTE_CLOSED:
                p.extra_routes = routes[1:]
    if p.type == EventType.FARE_HIKE:
        p.fare = find_fare(norm, spans)
    else:
        p.sacco = None if p.type else p.sacco
    return p


# --------------------------------------------------------------------------- spam

def spam_reason(report, parsed, now):
    norm = _norm(report.raw_text)
    if report.raw_text and (
        any(_has(norm, w) for w in kw.BLOCKLIST_WORDS)
        or any(_has(norm, p) for p in kw.BLOCKLIST_PHRASES)
        or re.search(kw.URL_PATTERN, report.raw_text.lower())
    ):
        return "blocklist"
    if report.source == "sms" and (not parsed.type and not parsed.stage):
        return "unparseable"
    if report.source == "sms" and (not parsed.type or not parsed.route):
        return "unparseable"
    recent = Report.objects.filter(
        sender_phone=report.sender_phone,
        created_at__gte=now - timedelta(minutes=kw.RATE_LIMIT_MINUTES),
        created_at__lte=now,
    ).exclude(pk=report.pk).count()
    if recent >= kw.RATE_LIMIT_COUNT:
        return "rate_limit"
    return ""


# --------------------------------------------------------------------------- merge + verify

def find_open_event(report, now):
    qs = Event.objects.filter(
        route=report.route,
        type=report.type,
        status__in=OPEN_STATUSES,
        first_seen__gte=now - MERGE_WINDOW,
    ).order_by("-first_seen")
    for ev in qs:
        if ev.expires_at and ev.expires_at <= now:
            continue
        if report.stage_id and ev.stage_id and report.stage_id != ev.stage_id:
            continue
        if report.type == EventType.FARE_HIKE:
            if report.sacco_id != ev.sacco_id:
                continue
            if report.fare and ev.fare and abs(report.fare - ev.fare) > FARE_TOLERANCE:
                continue
        if report.type == EventType.ACCIDENT_POLICE and report.subtype and ev.subtype and report.subtype != ev.subtype:
            continue
        return ev
    return None


def reporter_phones(event):
    phones = set(
        event.reports.filter(is_spam=False).values_list("sender_phone", flat=True)
    )
    phones |= set(event.votes.filter(kind="still").values_list("user__phone", flat=True))
    return phones


def refresh_count(event):
    event.reporter_count = len(reporter_phones(event))
    return event.reporter_count


def maybe_verify(event, now, notify=True):
    if event.status == "pending" and event.reporter_count >= VERIFY_AT:
        event.status = "verified"
        event.verified_at = now
        event.save()
        write_alert(event, now, notify=notify)
        return True
    return False


def event_title(event):
    stage = event.stage.name if event.stage else event.route.destination
    if event.type == EventType.FARE_HIKE:
        sacco = event.sacco.sacco_name if event.sacco else "Fares"
        if event.previous_fare and event.fare:
            return f"Fare hike: {sacco} KES {event.previous_fare} → {event.fare}"
        return f"Fare hike: {sacco}" + (f" KES {event.fare}" if event.fare else "")
    if event.type == EventType.JAM:
        return f"Jam at {stage}"
    if event.type == EventType.ROUTE_CLOSED:
        return f"Route closed at {stage}"
    return f"{'Police check' if event.subtype == 'police' else 'Accident'} at {stage}"


def alert_text(event):
    if event.type == EventType.FARE_HIKE and event.sacco and event.fare:
        return f"Fare hike — {event.sacco.sacco_name} now KES {event.fare}"
    if event.type == EventType.ROUTE_CLOSED:
        return event_title(event).replace("Route closed at", "Route closed —")
    return event_title(event)


def affected_routes(event):
    return [event.route, *event.extra_routes.order_by("id")]


def write_alert(event, now, notify=True):
    routes = affected_routes(event)
    loud = event.type in (EventType.ROUTE_CLOSED, EventType.FARE_HIKE) or event.subtype == "accident"
    channel = "sms+push" if loud else "push"
    phones = set()
    for r in routes:
        phones |= set(r.subscribers.values_list("phone", flat=True))
    alert = Alert.objects.create(
        event=event,
        sent_at=now,
        channel=channel,
        routes_notified=", ".join(r.number for r in routes),
        recipients_count=len(phones),
    )
    if notify and "sms" in channel:
        text = f"MatatuPulse: {alert_text(event)} (Route {alert.routes_notified}). Verified by {event.reporter_count} commuters."
        for phone in phones:
            send_sms(phone, text, kind="alert")
    return alert


@transaction.atomic
def process_report(report, now=None, notify=True):
    """Parse, spam-check, merge and verify one report. Saves and returns the report."""
    now = now or timezone.now()
    if report.created_at is None:
        report.created_at = now

    if report.source == "sms":
        parsed = parse_sms(report.raw_text)
        report.type = parsed.type
        report.subtype = parsed.subtype
        report.stage = parsed.stage
        report.sacco = parsed.sacco
        report.route = parsed.route
        report.fare = parsed.fare
    else:
        # App reports arrive structured; we only look in the note for a stage.
        parsed = Parsed(type=report.type, route=report.route, sacco=report.sacco, fare=report.fare)
        if report.raw_text and not report.stage_id:
            report.stage, _ = find_stage(_norm(report.raw_text))
            if report.type == EventType.ACCIDENT_POLICE and not report.subtype:
                _, report.subtype = parse_type(_norm(report.raw_text))
        if report.type == EventType.ACCIDENT_POLICE and not report.subtype:
            report.subtype = "accident"
        if report.type == EventType.ROUTE_CLOSED and report.stage:
            parsed.extra_routes = list(report.stage.routes.exclude(pk=report.route_id))
        if report.type != EventType.FARE_HIKE:
            report.fare = None

    report.save()

    reason = spam_reason(report, parsed, now)
    if reason:
        report.is_spam = True
        report.spam_reason = reason
        report.save(update_fields=["is_spam", "spam_reason"])
        return report

    event = find_open_event(report, now)
    if event is None:
        ttl = ttl_for(report.type, report.subtype)
        event = Event.objects.create(
            type=report.type,
            subtype=report.subtype,
            route=report.route,
            sacco=report.sacco,
            stage=report.stage,
            fare=report.fare,
            previous_fare=(sacco_fare(report.sacco, now)["fare"] if report.sacco else None),
            note=report.raw_text,
            first_seen=now,
            last_seen=now,
            expires_at=(now + ttl) if ttl else None,
        )
        if parsed.extra_routes:
            event.extra_routes.set(parsed.extra_routes)
    else:
        if not event.stage_id and report.stage_id:
            event.stage = report.stage
        if not event.note and report.raw_text:
            event.note = report.raw_text
        if report.type == EventType.FARE_HIKE and report.fare and event.status == "pending":
            event.fare = report.fare  # latest wins while pending
        event.last_seen = now
        ttl = ttl_for(event.type, event.subtype)
        if ttl:
            event.expires_at = max(event.expires_at or now, now + ttl)

    report.event = event
    report.save(update_fields=["event", "stage"])
    refresh_count(event)
    event.save()
    maybe_verify(event, now, notify=notify)
    return report


@transaction.atomic
def cast_vote(event, user, kind, now=None, notify=True):
    now = now or timezone.now()
    Vote.objects.update_or_create(event=event, user=user, defaults={"kind": kind, "created_at": now})
    event.refresh_from_db()
    if kind == "still" and event.status in OPEN_STATUSES:
        ttl = ttl_for(event.type, event.subtype)
        if ttl:
            event.expires_at = max(event.expires_at or now, now + ttl)
        event.last_seen = now
    refresh_count(event)
    if event.status in OPEN_STATUSES and event.votes.filter(kind="cleared").count() >= CLEAR_AT:
        event.status = "cleared"
        event.cleared_at = now
    event.save()
    maybe_verify(event, now, notify=notify)
    return event


# --------------------------------------------------------------------------- read-side

def expire_stale(now=None):
    now = now or timezone.now()
    return Event.objects.filter(status__in=OPEN_STATUSES, expires_at__lte=now).update(status="expired")


def active_events(route=None, now=None):
    now = now or timezone.now()
    qs = Event.objects.filter(status__in=OPEN_STATUSES).select_related("route", "sacco", "stage")
    if route is not None:
        from django.db.models import Q
        qs = qs.filter(Q(route=route) | Q(extra_routes=route)).distinct()
    return [e for e in qs if not e.expires_at or e.expires_at > now]


def sacco_fare(rs, now=None, events=None):
    """Derived fare for one sacco: verified hike > pending hike ('KES 90?') > usual fare."""
    now = now or timezone.now()
    if events is None:
        events = [e for e in active_events(rs.route, now) if e.type == EventType.FARE_HIKE]
    mine = sorted(
        (e for e in events if e.sacco_id == rs.id and e.fare),
        key=lambda e: e.last_seen,
        reverse=True,
    )
    verified = [e for e in mine if e.status == "verified"]
    pending = [e for e in mine if e.status == "pending"]
    if verified:
        e = verified[0]
        return {"fare": e.fare, "state": "up" if e.fare >= rs.usual_fare else "down",
                "delta": e.fare - rs.usual_fare, "event": e}
    if pending:
        e = pending[0]
        return {"fare": e.fare, "state": "pending", "delta": e.fare - rs.usual_fare, "event": e}
    return {"fare": rs.usual_fare, "state": "normal", "delta": 0, "event": None}


KWAMA_TYPES = (EventType.ROUTE_CLOSED, EventType.JAM)


def is_banner_event(e):
    return e.status == "verified" and (
        e.type == EventType.ROUTE_CLOSED
        or (e.type == EventType.ACCIDENT_POLICE and e.subtype == "accident")
    )


def route_pill(events):
    """events: active events on one route."""
    if any(
        e.status == "verified" and (e.type in KWAMA_TYPES or is_banner_event(e)) for e in events
    ):
        return "kwama"
    if events:
        return "moderate"
    return "maji_safi"
