from django.conf import settings
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User, mask_phone_intl, normalize_phone
from .otp import request_code, verify_code


class OtpThrottle(SimpleRateThrottle):
    """Per-IP cap on OTP endpoints (rate: THROTTLE_OTP)."""

    scope = "otp"

    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}


def user_payload(user):
    return {
        "id": user.id,
        "phone": user.phone,
        "phone_masked": mask_phone_intl(user.phone),
        "is_staff": user.is_staff,
    }


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([OtpThrottle])
def otp_request(request):
    phone = normalize_phone(request.data.get("phone"))
    if not phone:
        return Response({"detail": "Enter a valid Kenyan phone number."}, status=status.HTTP_400_BAD_REQUEST)
    result = request_code(phone)
    if not result.ok:
        headers = {"Retry-After": str(result.retry_after)} if result.retry_after else {}
        return Response(
            {"detail": result.detail, "retry_after": result.retry_after}, status=result.status, headers=headers
        )
    return Response({
        "sent": True,
        "phone": phone,
        "demo": result.demo,
        "resend_in": settings.OTP_RESEND_SECONDS,
        "expires_in": settings.OTP_TTL_SECONDS,
    })


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([OtpThrottle])
def otp_verify(request):
    phone = normalize_phone(request.data.get("phone"))
    code = str(request.data.get("code", "")).strip()
    if not phone or len(code) != 4 or not code.isdigit():
        return Response({"detail": "Enter the 4-digit code."}, status=status.HTTP_400_BAD_REQUEST)
    if not verify_code(phone, code):
        return Response({"detail": "That code is wrong or has expired."}, status=status.HTTP_400_BAD_REQUEST)

    user, _ = User.objects.get_or_create(phone=phone)
    refresh = RefreshToken.for_user(user)
    return Response({"access": str(refresh.access_token), "refresh": str(refresh), "user": user_payload(user)})


@api_view(["GET"])
def me(request):
    return Response(user_payload(request.user))
