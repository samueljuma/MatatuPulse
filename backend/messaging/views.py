import hmac

from django.conf import settings
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .service import apply_delivery_report


def webhook_token_ok(request):
    """Webhooks carry ?token=SMS_WEBHOOK_TOKEN. Open only when no token is configured (dev)."""
    expected = settings.SMS_WEBHOOK_TOKEN
    if not expected:
        return settings.DEBUG
    given = request.query_params.get("token") or request.headers.get("X-Webhook-Token", "")
    return hmac.compare_digest(str(given), expected)


@api_view(["POST"])
@permission_classes([AllowAny])
def delivery_report(request):
    if not webhook_token_ok(request):
        return Response({"detail": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)
    data = request.data.dict() if hasattr(request.data, "dict") else dict(request.data)
    msg = apply_delivery_report(data)
    return Response({"ok": True, "matched": bool(msg)})
