"""MatatuPulse settings. Everything deploy-specific comes from environment variables."""

import os
import sys
from datetime import timedelta
from pathlib import Path

import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_dotenv(path):
    """Tiny .env loader (KEY=VALUE lines) so local secrets stay out of the shell history."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.split(" #", 1)[0].strip().strip('"').strip("'")
        os.environ.setdefault(key.strip(), value)


_load_dotenv(BASE_DIR / ".env")


def env_bool(name, default=False):
    return os.environ.get(name, str(default)).lower() in ("1", "true", "yes", "on")


def env_list(name, default=""):
    return [x.strip() for x in os.environ.get(name, default).split(",") if x.strip()]


DEBUG = env_bool("DEBUG", True)
SECRET_KEY = os.environ.get("SECRET_KEY", "")
if not SECRET_KEY:
    if not DEBUG:
        raise RuntimeError("SECRET_KEY must be set when DEBUG is false")
    SECRET_KEY = "dev-only-insecure-key-change-me-before-deploying-matatupulse"
ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "*" if DEBUG else "")
if not DEBUG and not ALLOWED_HOSTS:
    raise RuntimeError("ALLOWED_HOSTS must be set when DEBUG is false")

# Demo mode keeps the pitch tools on: /api/demo/replay and the seeded SMS replay.
DEMO_MODE = env_bool("DEMO_MODE", DEBUG)
DEMO_OTP = "4729"

# --- OTP
# Numbers in OTP_TEST_NUMBERS skip SMS and accept DEMO_OTP (judges, rehearsals, tests).
OTP_TEST_NUMBERS = env_list("OTP_TEST_NUMBERS")
OTP_TTL_SECONDS = int(os.environ.get("OTP_TTL_SECONDS", 300))
OTP_RESEND_SECONDS = int(os.environ.get("OTP_RESEND_SECONDS", 30))
OTP_MAX_PER_HOUR = int(os.environ.get("OTP_MAX_PER_HOUR", 5))
OTP_MAX_ATTEMPTS = int(os.environ.get("OTP_MAX_ATTEMPTS", 5))

# --- SMS: console (logs only) or thrivewave
# Master kill switch (from the Mat3Route team's backend): SMS_ENABLED=false stops every real SMS
# (OTPs fail with 503, alerts are logged as failed). On by default so deployed logins keep working.
SMS_ENABLED = env_bool("SMS_ENABLED", True)
SMS_PROVIDER = os.environ.get("SMS_PROVIDER", "console").strip().strip(",;").lower()
THRIVEWAVE_API_KEY = os.environ.get("THRIVEWAVE_API_KEY", "")
THRIVEWAVE_BASE_URL = os.environ.get("THRIVEWAVE_BASE_URL", "https://sms.thrivevas.com")
THRIVEWAVE_SMS_PATH = os.environ.get("THRIVEWAVE_SMS_PATH", "/v1/message/send")
THRIVEWAVE_SENDER_ID = os.environ.get("THRIVEWAVE_SENDER_ID", "")
THRIVEWAVE_CALLBACK_URL = os.environ.get("THRIVEWAVE_CALLBACK_URL", "")
THRIVEWAVE_TIMEOUT_SECONDS = float(os.environ.get("THRIVEWAVE_TIMEOUT_SECONDS", 10))
# Shared secret for /api/sms/inbound and /api/sms/delivery (?token=...).
SMS_WEBHOOK_TOKEN = os.environ.get("SMS_WEBHOOK_TOKEN", "")

# Never send real SMS or touch a real database from the test suite, whatever .env says.
if len(sys.argv) > 1 and sys.argv[1] == "test":
    SMS_PROVIDER = "console"
    SMS_WEBHOOK_TOKEN = "test-webhook-token"
    OTP_TEST_NUMBERS = []

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "messaging",
    "corsheaders",
    "accounts",
    "transit",
    "reports",
]

MIDDLEWARE = [
    "config.middleware.HealthCheckMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}", conn_max_age=600
    )
}

# Tests never touch the database in DATABASE_URL (it may be the live one); use local SQLite
# unless TEST_DATABASE_URL is set on purpose.
if len(sys.argv) > 1 and sys.argv[1] == "test":
    DATABASES = {
        "default": dj_database_url.parse(os.environ["TEST_DATABASE_URL"])
        if os.environ.get("TEST_DATABASE_URL")
        else {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "test-db.sqlite3"}
    }

AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = []

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Africa/Nairobi"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# The built React app. In the container it's copied to /app/frontend_dist; locally it's ../frontend/dist.
FRONTEND_DIST = Path(os.environ.get("FRONTEND_DIST", BASE_DIR.parent / "frontend" / "dist"))
# WhiteNoise serves the app's files (/assets/*, /favicon.svg) from the site root.
WHITENOISE_ROOT = FRONTEND_DIST if FRONTEND_DIST.exists() else None
WHITENOISE_INDEX_FILE = False  # index.html goes through spa_index so it's never cached


def _immutable_file_test(path, url):
    # Vite puts a content hash in every file under /assets/, so they can be cached forever.
    return url.startswith("/assets/")


WHITENOISE_IMMUTABLE_FILE_TEST = _immutable_file_test
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS", "http://localhost:5173")
CORS_ALLOW_ALL_ORIGINS = DEBUG and env_bool("CORS_ALLOW_ALL", True)
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS") or [
    f"https://{h.lstrip('.')}" for h in ALLOWED_HOSTS if h not in ("*", "localhost", "127.0.0.1")
]  # the Django admin form posts from the app's own https origin

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    # The platform terminates HTTPS. Only redirect here if it forwards X-Forwarded-Proto.
    SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", False)
    SECURE_HSTS_SECONDS = int(os.environ.get("SECURE_HSTS_SECONDS", 60 * 60 * 24 * 30))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = False
    SILENCED_SYSTEM_CHECKS = ["security.W021"]  # preload list is opt-in; not for a hackathon domain
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_CONTENT_TYPE_NOSNIFF = True

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_THROTTLE_RATES": {
        "otp": os.environ.get("THROTTLE_OTP", "20/hour"),
        "reports": os.environ.get("THROTTLE_REPORTS", "60/hour"),
        "sms_inbound": os.environ.get("THROTTLE_SMS_INBOUND", "600/minute"),
    },
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=12),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=30),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "loggers": {
        "matatupulse": {"handlers": ["console"], "level": "INFO"},
        "django.request": {"handlers": ["console"], "level": "WARNING"},
    },
}
