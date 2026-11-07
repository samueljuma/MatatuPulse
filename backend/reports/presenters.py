"""JSON shapes the React app consumes. Keep in sync with frontend/src/mocks/*.json."""

from django.db.models import Max, Q
from django.utils import timezone

from accounts.models import mask_phone
from transit.models import Route

from .models import Event, EventType, Report
from .services import (
    VERIFY_AT,
    active_events,
    event_title,
    is_banner_event,
    route_pill,
    sacco_fare,
)

TYPE_LABELS = {
    EventType.FARE_HIKE: "Fare hike",
    EventType.JAM: "Jam / Stall",
    EventType.ROUTE_CLOSED: "Route closed",
}
SHORT_LABELS = {
    EventType.FARE_HIKE: "Fare",
    EventType.JAM: "Jam",
    EventType.ROUTE_CLOSED: "Closed",
}


def type_label(event):
    if event.type == EventType.ACCIDENT_POLICE:
        return "Police check" if event.subtype == "police" else "Accident"
    return TYPE_LABELS.get(event.type, event.type)


def short_label(obj):
    if obj.type == EventType.ACCIDENT_POLICE:
        return "Police" if obj.subtype == "police" else "Accident"
    return SHORT_LABELS.get(obj.type, "")


def iso(dt):
    return dt.isoformat() if dt else None


def event_card(event, user=None):
    my_vote = None
    i_reported = False
    if user is not None and getattr(user, "is_authenticated", False):
        vote = next((v for v in event.votes.all() if v.user_id == user.id), None)
        my_vote = vote.kind if vote else None
        i_reported = event.reports.filter(sender_phone=user.phone, is_spam=False).exists()
    return {
        "id": event.id,
        "ref": event.ref,
        "type": event.type,
        "subtype": event.subtype,
        "label": type_label(event),
        "title": event_title(event),
        "stage": event.stage.name if event.stage else None,
        "sacco": event.sacco.sacco_name if event.sacco else None,
        "sacco_id": event.sacco_id,
        "fare": event.fare,
        "previous_fare": event.previous_fare,
        "note": event.note,
        "status": event.status,
        "confirmations": event.reporter_count,
        "needed": max(0, VERIFY_AT - event.reporter_count),
        "cleared_votes": sum(1 for v in event.votes.all() if v.kind == "cleared"),
        "first_seen": iso(event.first_seen),
        "last_seen": iso(event.last_seen),
        "verified_at": iso(event.verified_at),
        "expires_at": iso(event.expires_at),
        "my_vote": my_vote,
        "i_reported": i_reported,
    }


def banner(events, user=None):
    candidates = sorted((e for e in events if is_banner_event(e)), key=lambda e: e.verified_at, reverse=True)
    if not candidates:
        return None
    e = candidates[0]
    return {
        "event_id": e.id,
        "title": event_title(e),
        "reports": e.reporter_count,
        "verified_at": iso(e.verified_at),
        "event": event_card(e, user),
    }


def route_updated_at(route):
    latest = Report.objects.filter(route=route, is_spam=False).aggregate(m=Max("created_at"))["m"]
    return iso(latest)


def route_summary(route, user=None, now=None, events=None):
    events = events if events is not None else active_events(route, now)
    subscribed = bool(user and user.is_authenticated and user.subscriptions.filter(pk=route.pk).exists())
    return {
        "id": route.id,
        "number": route.number,
        "name": route.name,
        "via": route.via,
        "line": route.line,
        "is_demo": route.is_demo,
        "destination": route.destination,
        "pill": route_pill(events),
        "alert_count": sum(1 for e in events if is_banner_event(e)),
        "subscribed": subscribed,
    }


def route_detail(route, user=None, now=None):
    now = now or timezone.now()
    events = active_events(route, now)
    fare_events = [e for e in events if e.type == EventType.FARE_HIKE]
    saccos = []
    for rs in route.saccos.all():
        f = sacco_fare(rs, now, fare_events)
        ev = f["event"]
        saccos.append({
            "id": rs.id,
            "name": rs.sacco_name,
            "usual_fare": rs.usual_fare,
            "fare_max": rs.fare_max,
            "fare": f["fare"],
            "state": f["state"],  # up | down | pending | normal
            "delta": f["delta"],
            "reporters": ev.reporter_count if ev else 0,
            "event_id": ev.id if ev else None,
            "updated_at": iso((ev.verified_at or ev.last_seen) if ev else None),
        })
    top = banner(events, user)
    listed = [e for e in events if not (top and e.id == top["event_id"])]
    listed.sort(key=lambda e: e.last_seen, reverse=True)
    return {
        **route_summary(route, user, now, events),
        "stages": [s.name for s in route.stages.order_by("routestage__order")],
        "saccos": saccos,
        "banner": top,
        "events": [event_card(e, user) for e in listed],
        "updated_at": route_updated_at(route),
    }


def routes_matching(search):
    qs = Route.objects.all()
    s = (search or "").strip()
    if not s:
        return list(qs)
    q = (
        Q(number__icontains=s)
        | Q(name__icontains=s)
        | Q(via__icontains=s)
        | Q(stages__name__icontains=s)
        | Q(saccos__sacco_name__icontains=s)
    )
    matched = list(qs.filter(q).distinct())
    # Also match stage aliases ("g45").
    from transit.models import Stage

    alias_hits = [st for st in Stage.objects.all() if any(s.lower() in a for a in st.aliases)]
    extra = Route.objects.filter(stages__in=alias_hits).distinct()
    ids = {r.id for r in matched}
    return matched + [r for r in extra if r.id not in ids]


# --------------------------------------------------------------------------- signal

def routes_label(event):
    numbers = [event.route.number, *event.extra_routes.order_by("id").values_list("number", flat=True)]
    return ("Routes " if len(numbers) > 1 else "Route ") + ", ".join(numbers)


def signal_payload(limit=60):
    reports = Report.objects.select_related("event").order_by("-created_at", "-id")[:limit]
    verified = (
        Event.objects.filter(verified_at__isnull=False)
        .select_related("route", "sacco", "stage")
        .order_by("-verified_at")
    )
    from .models import Alert

    alerts = Alert.objects.select_related("event", "event__route", "event__sacco", "event__stage")[:30]
    from .services import alert_text

    def channel_label(ch):
        return {"sms+push": "SMS + push", "sms": "SMS", "push": "push"}.get(ch, ch)

    def alert_status(e):
        return {"verified": "Active", "cleared": "Cleared", "expired": "Expired"}.get(e.status, e.status.title())

    return {
        "funnel": {
            "raw": Report.objects.count(),
            "spam": Report.objects.filter(is_spam=True).count(),
            "events": Event.objects.count(),
            "verified": Event.objects.filter(verified_at__isnull=False).count(),
        },
        "pending_count": Event.objects.filter(verified_at__isnull=True).count(),
        "reports": [
            {
                "id": r.id,
                "text": r.raw_text or f"[app] {short_label(r)}",
                "source": r.source,
                "phone": mask_phone(r.sender_phone),
                "at": iso(r.created_at),
                "is_spam": r.is_spam,
                "spam_reason": r.spam_reason,
                "event_ref": r.event.ref if r.event else None,
                "event_label": short_label(r.event) if r.event else None,
            }
            for r in reports
        ],
        "verified_events": [
            {
                "id": e.id,
                "ref": e.ref,
                "title": event_title(e),
                "routes": routes_label(e),
                "stage": e.stage.name if e.stage else None,
                "type": e.type,
                "status": e.status,
                "reports": e.reporter_count,
                "first_seen": iso(e.first_seen),
                "verified_at": iso(e.verified_at),
            }
            for e in verified
        ],
        "alerts": [
            {
                "id": a.id,
                "sent_at": iso(a.sent_at),
                "text": alert_text(a.event),
                "routes": a.routes_notified,
                "sent_to": f"Route {a.routes_notified} subscribers · {channel_label(a.channel)}",
                "recipients": a.recipients_count,
                "status": alert_status(a.event),
            }
            for a in alerts
        ],
    }
