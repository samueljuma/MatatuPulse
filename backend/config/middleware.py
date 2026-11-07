from django.db import connection
from django.http import JsonResponse


class HealthCheckMiddleware:
    """Answer /health before ALLOWED_HOSTS and SSL redirect run (Fly's checker uses the machine IP)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path == "/health":
            try:
                with connection.cursor() as cur:
                    cur.execute("SELECT 1")
                return JsonResponse({"ok": True})
            except Exception:
                return JsonResponse({"ok": False}, status=503)
        return self.get_response(request)
