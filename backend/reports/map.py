"""Public, read-only data for the live map (frontend/public/live-map.html).

Shapes match what the map page reads: routes with endpoints and a path, active incidents with
coordinates, and a route's current fare range. No phone numbers or user data are exposed.
"""

from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from transit.models import Route, RouteStage

from .models import EventType
from .presenters import iso, routes_label, type_label
from .services import active_events, event_title, expire_stale, sacco_fare

SEVERITY = {
    ("accident_police", "accident"): "high",
    ("route_closed", ""): "high",
    ("jam", ""): "medium",
    ("accident_police", "police"): "low",
    ("fare_hike", ""): "low",
}


def _stages(route):
    return [rs.stage for rs in route.routestage_set.all()]


def _endpoints(route, stages):
    parts = [p.strip() for p in route.name.split("→")]
    start = stages[0].name if stages else parts[0]
    end = stages[-1].name if stages else parts[-1]
    return start, end


@api_view(["GET"])
@permission_classes([AllowAny])
def map_routes(request):
    routes = Route.objects.prefetch_related(
        Prefetch("routestage_set", queryset=RouteStage.objects.select_related("stage").order_by("order")),
        "saccos",
    )
    out = []
    for r in routes:
        stages = _stages(r)
        start, end = _endpoints(r, stages)
        saccos = list(r.saccos.all())
        located = [s for s in stages if s.lat is not None and s.lon is not None]
        first, last = (stages[0], stages[-1]) if stages else (None, None)
        item = {
            "id": r.id,
            "route_number": r.number,
            "name": r.name,
            "line": r.line or (f"{r.via} (demo)" if r.is_demo else r.via) or "Other",
            "via": r.via,
            "start": start,
            "end": end,
            "sacco": saccos[0].sacco_name if len(saccos) == 1 else (f"{len(saccos)} saccos" if saccos else ""),
            "base_fare_min": min((s.usual_fare for s in saccos), default=None),
            "base_fare_max": max(((s.fare_max or s.usual_fare) for s in saccos), default=None),
            "start_lat": first.lat if first else None,
            "start_lon": first.lon if first else None,
            "end_lat": last.lat if last else None,
            "end_lon": last.lon if last else None,
            "is_demo": r.is_demo,
        }
        # Multi-stage (demo) routes get a path through their stages. Two-stage imported routes are
        # left to the map's embedded road geometry (keyed "start|end").
        if len(located) > 2:
            item["path"] = [[s.lat, s.lon] for s in located]
        out.append(item)
    return Response(out)


@api_view(["GET"])
@permission_classes([AllowAny])
def map_incidents(request):
    now = timezone.now()
    expire_stale(now)
    out = []
    for e in active_events(None, now):
        stage = e.stage
        out.append({
            "id": e.id,
            "ref": e.ref,
            "route_id": e.route_id,
            "routes": routes_label(e),
            "type": e.type,
            "label": type_label(e),
            "stage": stage.name if stage else None,
            "severity": SEVERITY.get((e.type, e.subtype if e.type == EventType.ACCIDENT_POLICE else ""), "low"),
            "status": e.status,
            "description": event_title(e) + (f" · “{e.note}”" if e.note else ""),
            "confirmations": e.reporter_count,
            "reported_at": iso(e.first_seen),
            "latitude": stage.lat if stage else None,
            "longitude": stage.lon if stage else None,
        })
    return Response(out)


@api_view(["GET"])
@permission_classes([AllowAny])
def map_route_fare(request, pk):
    """Current fare range on a route, from live sacco fares (verified hikes count; pending ones don't)."""
    now = timezone.now()
    route = get_object_or_404(Route, pk=pk)
    events = active_events(route, now)
    fare_events = [e for e in events if e.type == EventType.FARE_HIKE]
    usual_min = usual_max = cur_min = cur_max = None
    reasons = []
    for rs in route.saccos.all():
        f = sacco_fare(rs, now, fare_events)
        current = f["fare"] if f["state"] in ("up", "down") else rs.usual_fare
        current_max = current if f["state"] in ("up", "down") else (rs.fare_max or rs.usual_fare)
        usual_min = rs.usual_fare if usual_min is None else min(usual_min, rs.usual_fare)
        usual_max = (rs.fare_max or rs.usual_fare) if usual_max is None else max(usual_max, rs.fare_max or rs.usual_fare)
        cur_min = current if cur_min is None else min(cur_min, current)
        cur_max = current_max if cur_max is None else max(cur_max, current_max)
        if f["state"] in ("up", "down"):
            reasons.append(f"{rs.sacco_name} KES {rs.usual_fare} → {f['fare']} (verified)")
        elif f["state"] == "pending":
            reasons.append(f"{rs.sacco_name} KES {f['fare']}? (unverified)")
    reasons += [event_title(e) for e in events if e.status == "verified" and e.type != EventType.FARE_HIKE]
    multiplier = (cur_max / usual_max) if usual_max and cur_max else 1.0
    return Response({
        "route_id": route.id,
        "fare_min": cur_min,
        "fare_max": cur_max,
        "usual_min": usual_min,
        "usual_max": usual_max,
        "multiplier": round(multiplier, 2),
        "reasons": reasons or ["No verified changes. Usual fares apply."],
    })
