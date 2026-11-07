from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from rest_framework_simplejwt.views import TokenRefreshView

from accounts import views as accounts
from messaging import views as messaging
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
]

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", lambda r: JsonResponse({"service": "MatatuPulse API", "ok": True})),
    path("api/", include(api)),
]
