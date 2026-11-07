from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.decorators import api_view
from rest_framework.response import Response

from reports.presenters import route_detail as present_detail
from reports.presenters import route_summary, routes_matching
from reports.services import active_events, expire_stale

from .models import Route


@api_view(["GET"])
def route_list(request):
    now = timezone.now()
    expire_stale(now)
    routes = routes_matching(request.query_params.get("search"))
    return Response([route_summary(r, request.user, now) for r in routes])


@api_view(["GET"])
def route_detail(request, pk):
    now = timezone.now()
    expire_stale(now)
    route = get_object_or_404(Route, pk=pk)
    return Response(present_detail(route, request.user, now))


@api_view(["POST"])
def route_subscribe(request, pk):
    route = get_object_or_404(Route, pk=pk)
    user = request.user
    if user.subscriptions.filter(pk=route.pk).exists():
        user.subscriptions.remove(route)
        subscribed = False
    else:
        user.subscriptions.add(route)
        subscribed = True
    return Response({"subscribed": subscribed})
