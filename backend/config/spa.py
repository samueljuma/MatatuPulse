"""Serve the built React app (frontend/dist) from Django, so the whole product is one container."""

from django.conf import settings
from django.http import FileResponse, JsonResponse
from django.views.decorators.cache import never_cache


@never_cache
def spa_index(request, *args, **kwargs):
    """Any non-API path (/, /login, /routes/12, /signal) gets index.html; React Router takes it from there."""
    index = settings.FRONTEND_DIST / "index.html"
    if not index.exists():
        # Dev without a front-end build: Vite serves the app on :5173 instead.
        return JsonResponse({"service": "MatatuPulse API", "ok": True, "frontend": "not built"})
    return FileResponse(index.open("rb"), content_type="text/html; charset=utf-8")
