from django.contrib import admin
from django.urls import include, path, re_path
from rest_framework_simplejwt.views import TokenRefreshView

from accounts import views as accounts
from config.spa import spa_index
from messaging import views as messaging
from reports import map as live_map
from reports import views as reports
from transit import views as transit

api = [
    path("auth/otp/request", accounts.otp_request),
    path("auth/otp/verify", accounts.otp_verify),
    path("auth/refresh", TokenRefreshView.as_view()),
    path("auth/me", accounts.me),
    path("routes", transit.route_list),
    path("routes/<int:pk>", transit.route_detail),
    path("routes/<int:pk>/subscribe", transit.route_subscribe),
    path("reports", reports.create_report),
    path("events/<int:pk>/vote", reports.vote),
    path("sms/inbound", reports.sms_inbound),
    path("sms/delivery", messaging.delivery_report),
    path("signal", reports.signal),
    path("demo/replay", reports.demo_replay),
    # Public, read-only data for /live-map.html
    path("map/routes", live_map.map_routes),
    path("map/routes/<int:pk>/fare", live_map.map_route_fare),
    path("map/incidents", live_map.map_incidents),
]

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include(api)),
    # Everything else is the React app (its files are served by WhiteNoise from FRONTEND_DIST).
    re_path(r"^(?!api/|admin/|static/).*$", spa_index),
]
