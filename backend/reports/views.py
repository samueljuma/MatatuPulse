from django.conf import settings
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle

from accounts.models import normalize_phone
from messaging.views import webhook_token_ok
from transit.models import Route, RouteSacco

from .models import Event, EventType, Report
from .presenters import event_card, signal_payload
from .replay import replay
from .services import cast_vote, expire_stale, process_report


class ReportThrottle(SimpleRateThrottle):
    """Per-user cap on app reports (rate: THROTTLE_REPORTS); process_report adds the per-phone spam rule."""

    scope = "reports"

    def get_cache_key(self, request, view):
        ident = request.user.pk if request.user and request.user.is_authenticated else self.get_ident(request)
        return self.cache_format % {"scope": self.scope, "ident": ident}


class SmsInboundThrottle(SimpleRateThrottle):
    scope = "sms_inbound"

    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}


@api_view(["POST"])
@throttle_classes([ReportThrottle])
def create_report(request):
    data = request.data
    route = get_object_or_404(Route, pk=data.get("route"))
    type_ = data.get("type")
    if type_ not in EventType.values:
        return Response({"detail": "Pick what's happening."}, status=status.HTTP_400_BAD_REQUEST)

    sacco = None
    if data.get("sacco"):
        sacco = get_object_or_404(RouteSacco, pk=data["sacco"], route=route)

    fare = None
    if type_ == EventType.FARE_HIKE:
        try:
            fare = int(data.get("fare"))
        except (TypeError, ValueError):
            return Response({"detail": "Enter the new fare."}, status=status.HTTP_400_BAD_REQUEST)
        if not 10 <= fare <= 999:
            return Response({"detail": "That fare doesn't look right."}, status=status.HTTP_400_BAD_REQUEST)

    note = (data.get("note") or "").strip()[:280]
    subtype = data.get("subtype") if data.get("subtype") in ("accident", "police") else ""
    report = Report(
        user=request.user,
        sender_phone=request.user.phone,
        source="app",
        raw_text=note,
        type=type_,
        subtype=subtype,
        route=route,
        sacco=sacco,
        fare=fare,
    )
    now = timezone.now()
    process_report(report, now=now)

    if report.is_spam:
        msg = {
            "rate_limit": "You've sent a lot of reports in a few minutes. Try again shortly.",
            "blocklist": "That note looks like spam, so we didn't post it.",
        }.get(report.spam_reason, "We couldn't use that report.")
        return Response({"detail": msg, "spam_reason": report.spam_reason}, status=status.HTTP_429_TOO_MANY_REQUESTS
                        if report.spam_reason == "rate_limit" else status.HTTP_400_BAD_REQUEST)

    event = Event.objects.select_related("route", "sacco", "stage").get(pk=report.event_id)
    earlier = event.reports.filter(is_spam=False).exclude(pk=report.pk)
    verified_now = event.status == "verified" and event.verified_at == now
    return Response(
        {
            "event": event_card(event, request.user),
            "others_count": max(0, event.reporter_count - 1),
            "merged_count": earlier.count(),
            "verified_now": verified_now,
            "route_number": route.number,
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["POST"])
def vote(request, pk):
    event = get_object_or_404(Event, pk=pk)
    kind = request.data.get("kind")
    if kind not in ("still", "cleared"):
        return Response({"detail": "kind must be still or cleared."}, status=status.HTTP_400_BAD_REQUEST)
    if event.status not in ("pending", "verified"):
        return Response({"detail": "This report is no longer active."}, status=status.HTTP_409_CONFLICT)
    event = cast_vote(event, request.user, kind)
    return Response(event_card(event, request.user))


def _first(data, keys):
    for k in keys:
        v = data.get(k)
        if v not in (None, ""):
            return str(v)
    return ""


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([SmsInboundThrottle])
def sms_inbound(request):
    """Incoming-SMS webhook (ThriveWave or any gateway). Needs ?token=SMS_WEBHOOK_TOKEN."""
    if not webhook_token_ok(request):
        return Response({"detail": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)
    raw_from = _first(request.data, ("from", "msisdn", "phone", "sender", "source", "MSISDN"))
    phone = normalize_phone(raw_from) or raw_from[:16]
    text = _first(request.data, ("text", "message", "body", "content", "sms", "MESSAGE"))[:480]
    if not phone or not text:
        return Response({"detail": "from and text are required."}, status=status.HTTP_400_BAD_REQUEST)
    report = Report(source="sms", sender_phone=phone, raw_text=text)
    process_report(report)
    return Response({
        "ok": True,
        "spam": report.is_spam,
        "event": report.event.ref if report.event_id else None,
    })


@api_view(["GET"])
@permission_classes([AllowAny])
def signal(request):
    expire_stale(timezone.now())
    return Response(signal_payload())


@api_view(["POST"])
@permission_classes([IsAdminUser])
def demo_replay(request):
    if not settings.DEMO_MODE:
        return Response({"detail": "Replay is off (DEMO_MODE=false)."}, status=status.HTTP_403_FORBIDDEN)
    return Response(replay())

