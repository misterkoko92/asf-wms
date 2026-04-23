import os
import secrets
import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from django.core.exceptions import ImproperlyConfigured
from django.utils.translation import gettext_lazy as _

BASE_DIR = Path(__file__).resolve().parent.parent


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _env_list(name: str) -> list[str]:
    value = os.environ.get(name, "")
    return [item.strip() for item in value.split(",") if item.strip()]


def _env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _env_float(name: str, default: float) -> float:
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _env_optional_float(name: str) -> float | None:
    value = os.environ.get(name)
    if value is None or not value.strip():
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _is_secure_secret_key(secret_key: str) -> bool:
    if not secret_key:
        return False
    if secret_key.startswith("django-insecure-"):
        return False
    if len(secret_key) < 50:
        return False
    if len(set(secret_key)) < 5:
        return False
    return True


_SENTRY_SENSITIVE_KEY_PARTS = (
    "api_key",
    "authorization",
    "cookie",
    "csrf",
    "dsn",
    "password",
    "secret",
    "token",
)
_SENTRY_FILTERED = "[Filtered]"


def _sentry_redact_value(key: str, value):
    normalized = key.lower().replace("-", "_")
    if any(part in normalized for part in _SENTRY_SENSITIVE_KEY_PARTS):
        return _SENTRY_FILTERED
    if isinstance(value, dict):
        return {
            nested_key: _sentry_redact_value(str(nested_key), nested_value)
            for nested_key, nested_value in value.items()
        }
    if isinstance(value, list):
        return [_sentry_redact_value(key, nested_value) for nested_value in value]
    return value


def _sentry_strip_query(url: str) -> str:
    parsed = urlsplit(url)
    if not parsed.query:
        return url
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", parsed.fragment))


def _sentry_before_send(event, hint):
    request = event.get("request")
    if isinstance(request, dict):
        if isinstance(request.get("url"), str):
            request["url"] = _sentry_strip_query(request["url"])
        if request.get("query_string"):
            request["query_string"] = _SENTRY_FILTERED
        for section in ("headers", "cookies", "data", "env"):
            if isinstance(request.get(section), dict):
                if section == "cookies":
                    request[section] = {key: _SENTRY_FILTERED for key in request[section]}
                else:
                    request[section] = {
                        key: _sentry_redact_value(str(key), value)
                        for key, value in request[section].items()
                    }
            elif request.get(section):
                request[section] = _SENTRY_FILTERED

    for section in ("extra", "contexts"):
        if isinstance(event.get(section), dict):
            event[section] = {
                key: _sentry_redact_value(str(key), value) for key, value in event[section].items()
            }

    return event


def _validate_sentry_rate(name: str, value: float | None) -> None:
    if value is None:
        return
    if not 0.0 <= value <= 1.0:
        raise ImproperlyConfigured(f"{name} must be between 0.0 and 1.0.")


SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "").strip()

DEBUG = _env_bool("DJANGO_DEBUG", False)
RUNNING_TESTS = "test" in sys.argv

if not SECRET_KEY:
    if RUNNING_TESTS:
        SECRET_KEY = secrets.token_urlsafe(64)
    else:
        raise ImproperlyConfigured(
            "DJANGO_SECRET_KEY environment variable is required. "
            'Generate a strong key with: python -c "import secrets; '
            'print(secrets.token_urlsafe(64))"'
        )

if not DEBUG and not RUNNING_TESTS and not _is_secure_secret_key(SECRET_KEY):
    raise ImproperlyConfigured(
        "DJANGO_SECRET_KEY must be a strong, non-default value when DJANGO_DEBUG=false."
    )

SENTRY_DSN = os.environ.get("SENTRY_DSN", "").strip()
SENTRY_ENVIRONMENT = os.environ.get(
    "SENTRY_ENVIRONMENT", "development" if DEBUG else "production"
).strip() or ("development" if DEBUG else "production")
SENTRY_RELEASE = os.environ.get("SENTRY_RELEASE", "").strip()
SENTRY_SAMPLE_RATE = _env_float("SENTRY_SAMPLE_RATE", 1.0)
SENTRY_TRACES_SAMPLE_RATE = _env_optional_float("SENTRY_TRACES_SAMPLE_RATE")
SENTRY_SEND_DEFAULT_PII = _env_bool("SENTRY_SEND_DEFAULT_PII", False)
if SENTRY_DSN and not RUNNING_TESTS:
    _validate_sentry_rate("SENTRY_SAMPLE_RATE", SENTRY_SAMPLE_RATE)
    _validate_sentry_rate("SENTRY_TRACES_SAMPLE_RATE", SENTRY_TRACES_SAMPLE_RATE)
    try:
        import sentry_sdk
        from sentry_sdk.integrations.django import DjangoIntegration
    except ImportError as exc:
        raise ImproperlyConfigured(
            "SENTRY_DSN is configured but sentry-sdk is not installed."
        ) from exc

    sentry_options = {
        "dsn": SENTRY_DSN,
        "environment": SENTRY_ENVIRONMENT,
        "integrations": [DjangoIntegration()],
        "sample_rate": SENTRY_SAMPLE_RATE,
        "send_default_pii": SENTRY_SEND_DEFAULT_PII,
        "max_request_body_size": "never",
        "include_local_variables": False,
        "before_send": _sentry_before_send,
        "before_send_transaction": _sentry_before_send,
    }
    if SENTRY_RELEASE:
        sentry_options["release"] = SENTRY_RELEASE
    if SENTRY_TRACES_SAMPLE_RATE is not None:
        sentry_options["traces_sample_rate"] = SENTRY_TRACES_SAMPLE_RATE
    sentry_sdk.init(**sentry_options)

ALLOWED_HOSTS: list[str] = _env_list("DJANGO_ALLOWED_HOSTS")
SITE_BASE_URL = os.environ.get("SITE_BASE_URL", "").strip()

SECURE_SSL_REDIRECT = _env_bool(
    "SECURE_SSL_REDIRECT",
    not DEBUG and not RUNNING_TESTS,
)
SESSION_COOKIE_SECURE = _env_bool(
    "SESSION_COOKIE_SECURE",
    not DEBUG and not RUNNING_TESTS,
)
CSRF_COOKIE_SECURE = _env_bool(
    "CSRF_COOKIE_SECURE",
    not DEBUG and not RUNNING_TESTS,
)
SESSION_COOKIE_HTTPONLY = _env_bool("SESSION_COOKIE_HTTPONLY", True)
SESSION_COOKIE_SAMESITE = os.environ.get("SESSION_COOKIE_SAMESITE", "Strict").strip() or "Strict"
CSRF_COOKIE_HTTPONLY = _env_bool("CSRF_COOKIE_HTTPONLY", True)
CSRF_COOKIE_SAMESITE = os.environ.get("CSRF_COOKIE_SAMESITE", "Strict").strip() or "Strict"
SECURE_HSTS_SECONDS = int(os.environ.get("SECURE_HSTS_SECONDS", "0" if DEBUG else "31536000"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = _env_bool("SECURE_HSTS_INCLUDE_SUBDOMAINS", not DEBUG)
SECURE_HSTS_PRELOAD = _env_bool("SECURE_HSTS_PRELOAD", not DEBUG)
SECURE_CONTENT_TYPE_NOSNIFF = _env_bool("SECURE_CONTENT_TYPE_NOSNIFF", True)
X_FRAME_OPTIONS = os.environ.get("X_FRAME_OPTIONS", "DENY")
SECURE_REFERRER_POLICY = os.environ.get("SECURE_REFERRER_POLICY", "same-origin")
CSRF_TRUSTED_ORIGINS = _env_list("CSRF_TRUSTED_ORIGINS")
DATA_UPLOAD_MAX_NUMBER_FIELDS = _env_int("DATA_UPLOAD_MAX_NUMBER_FIELDS", 5000)
CSP_REPORT_ONLY_ENABLED = _env_bool("CSP_REPORT_ONLY_ENABLED", True)
# Emitted as the Content-Security-Policy-Report-Only response header.
CONTENT_SECURITY_POLICY_REPORT_ONLY = os.environ.get(
    "CONTENT_SECURITY_POLICY_REPORT_ONLY",
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' 'wasm-unsafe-eval' https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; "
    "font-src 'self' https://fonts.gstatic.com https://cdn.jsdelivr.net data:; "
    "img-src 'self' data: blob:; "
    "connect-src 'self' https://nominatim.openstreetmap.org https://cdn.jsdelivr.net; "
    "worker-src 'self' blob: https://cdn.jsdelivr.net; "
    "object-src 'none'; "
    "base-uri 'self'; "
    "frame-ancestors 'none'; "
    "form-action 'self'",
).strip()
if _env_bool("USE_PROXY_SSL_HEADER", not DEBUG):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
TRUSTED_PROXY_IPS: list[str] = _env_list("TRUSTED_PROXY_IPS")
DOCUMENT_SCAN_BACKEND = (
    os.environ.get("DOCUMENT_SCAN_BACKEND", "clamav").strip().lower() or "clamav"
)
if DOCUMENT_SCAN_BACKEND == "noop" and not RUNNING_TESTS:
    raise ImproperlyConfigured(
        "DOCUMENT_SCAN_BACKEND=noop is only allowed in tests. "
        "Use 'clamav' (or another real backend) in production."
    )
DOCUMENT_SCAN_CLAMAV_COMMAND = (
    os.environ.get("DOCUMENT_SCAN_CLAMAV_COMMAND", "clamscan").strip() or "clamscan"
)
DOCUMENT_SCAN_TIMEOUT_SECONDS = _env_int("DOCUMENT_SCAN_TIMEOUT_SECONDS", 30)
DOCUMENT_SCAN_QUEUE_PROCESSING_TIMEOUT_SECONDS = _env_int(
    "DOCUMENT_SCAN_QUEUE_PROCESSING_TIMEOUT_SECONDS", 900
)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "contacts",
    "wms.apps.WmsConfig",
    "api",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "wms.security_headers.ContentSecurityPolicyReportOnlyMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "asf_wms.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "wms.context_processors.admin_notifications",
                "wms.context_processors.ui_context",
            ],
        },
    },
]

WSGI_APPLICATION = "asf_wms.wsgi.application"
TEST_RUNNER = "asf_wms.test_runner.LanguageResetDiscoverRunner"

USE_MYSQL_FOR_TESTS = _env_bool("USE_MYSQL_FOR_TESTS")
USE_SQLITE_FOR_TESTS = RUNNING_TESTS and not USE_MYSQL_FOR_TESTS

DB_NAME = os.environ.get("DB_NAME")
if DB_NAME and not USE_SQLITE_FOR_TESTS:
    DATABASES = {
        "default": {
            "ENGINE": os.environ.get(
                "DB_ENGINE",
                "django.db.backends.mysql",
            ),
            "NAME": DB_NAME,
            "USER": os.environ.get("DB_USER", ""),
            "PASSWORD": os.environ.get("DB_PASSWORD", ""),
            "HOST": os.environ.get("DB_HOST", "localhost"),
            "PORT": os.environ.get("DB_PORT", "3306"),
            "OPTIONS": {"charset": "utf8mb4"},
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 12},
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

if RUNNING_TESTS:
    # Keep MD5 first for fast test user/password setup while preserving
    # compatibility with hashes that may still be asserted or checked in tests.
    PASSWORD_HASHERS = [
        "django.contrib.auth.hashers.MD5PasswordHasher",
        "django.contrib.auth.hashers.PBKDF2PasswordHasher",
        "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
        "django.contrib.auth.hashers.Argon2PasswordHasher",
        "django.contrib.auth.hashers.BCryptSHA256PasswordHasher",
        "django.contrib.auth.hashers.ScryptPasswordHasher",
    ]

LANGUAGE_CODE = "fr"
LANGUAGES = [
    ("fr", _("Français")),
    ("en", _("English")),
]
LOCALE_PATHS = [BASE_DIR / "locale"]
TIME_ZONE = "Europe/Paris"
USE_I18N = True
USE_TZ = True

DATE_FORMAT = "d/m/Y"
DATETIME_FORMAT = "d/m/Y H:i"
TIME_FORMAT = "H:i"
SHORT_DATE_FORMAT = "d/m/Y"
SHORT_DATETIME_FORMAT = "d/m/Y H:i"

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

EMAIL_BACKEND = os.environ.get("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "no-reply@example.com")
EMAIL_HOST = os.environ.get("EMAIL_HOST", "")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = _env_bool("EMAIL_USE_TLS", True)
EMAIL_USE_SSL = _env_bool("EMAIL_USE_SSL", False)
EMAIL_DELIVERY_MODE = (
    os.environ.get("EMAIL_DELIVERY_MODE", "direct_or_queue").strip().lower() or "direct_or_queue"
)
BREVO_API_KEY = os.environ.get("BREVO_API_KEY", "")
BREVO_SENDER_EMAIL = os.environ.get("BREVO_SENDER_EMAIL", "")
BREVO_SENDER_NAME = os.environ.get("BREVO_SENDER_NAME", "")
BREVO_REPLY_TO_EMAIL = os.environ.get("BREVO_REPLY_TO_EMAIL", "")
ORDER_NOTIFICATION_GROUP_NAME = os.environ.get(
    "ORDER_NOTIFICATION_GROUP_NAME", "Mail_Order_Staff"
).strip()
ACCOUNT_REQUEST_VALIDATION_GROUP_NAME = os.environ.get(
    "ACCOUNT_REQUEST_VALIDATION_GROUP_NAME", "Account_User_Validation"
).strip()
SHIPMENT_STATUS_UPDATE_GROUP_NAME = os.environ.get(
    "SHIPMENT_STATUS_UPDATE_GROUP_NAME", "Shipment_Status_Update"
).strip()
SHIPMENT_STATUS_CORRESPONDANT_GROUP_NAME = os.environ.get(
    "SHIPMENT_STATUS_CORRESPONDANT_GROUP_NAME",
    "Shipment_Status_Update_Correspondant",
).strip()

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

ENABLE_BASIC_AUTH = _env_bool("ENABLE_BASIC_AUTH", DEBUG)
_default_authentication_classes = [
    "rest_framework.authentication.SessionAuthentication",
]
if ENABLE_BASIC_AUTH:
    _default_authentication_classes.append("rest_framework.authentication.BasicAuthentication")

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": tuple(_default_authentication_classes),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_THROTTLE_CLASSES": (
        "rest_framework.throttling.UserRateThrottle",
        "rest_framework.throttling.AnonRateThrottle",
    ),
    "DEFAULT_THROTTLE_RATES": {
        "user": os.environ.get("DRF_USER_THROTTLE_RATE", "120/minute"),
        "anon": os.environ.get("DRF_ANON_THROTTLE_RATE", "30/minute"),
    },
}

ORG_NAME = os.environ.get("ORG_NAME", "ORG_NAME")
ORG_ADDRESS = os.environ.get("ORG_ADDRESS", "ORG_ADDRESS")
ORG_CONTACT = os.environ.get("ORG_CONTACT", "ORG_CONTACT")
ORG_SIGNATORY = os.environ.get("ORG_SIGNATORY", "ORG_SIGNATORY")

LOGIN_URL = "/admin/login/"
LOGIN_REDIRECT_URL = "/scan/"

SKU_PREFIX = os.environ.get("SKU_PREFIX", "ASF")
IMPORT_DEFAULT_PASSWORD = os.environ.get("IMPORT_DEFAULT_PASSWORD", "").strip()
INTEGRATION_API_KEY = os.environ.get("INTEGRATION_API_KEY", "").strip()
LISTING_MAX_FILE_SIZE_MB = int(os.environ.get("LISTING_MAX_FILE_SIZE_MB", "10"))
GRAPH_TENANT_ID = os.environ.get("GRAPH_TENANT_ID", "").strip()
GRAPH_CLIENT_ID = os.environ.get("GRAPH_CLIENT_ID", "").strip()
GRAPH_CLIENT_SECRET = os.environ.get("GRAPH_CLIENT_SECRET", "").strip()
GRAPH_DRIVE_ID = os.environ.get("GRAPH_DRIVE_ID", "").strip()
GRAPH_WORK_DIR = os.environ.get("GRAPH_WORK_DIR", "").strip()
GRAPH_REQUEST_TIMEOUT_SECONDS = _env_int("GRAPH_REQUEST_TIMEOUT_SECONDS", 30)
PRINT_PACK_TEMPLATE_DIRS = _env_list("PRINT_PACK_TEMPLATE_DIRS")
if not PRINT_PACK_TEMPLATE_DIRS:
    PRINT_PACK_TEMPLATE_DIRS = [str(BASE_DIR / "data" / "print_templates")]
PRINT_PACK_XLSX_FALLBACK_ENABLED = _env_bool("PRINT_PACK_XLSX_FALLBACK_ENABLED", False)
ACCOUNT_REQUEST_THROTTLE_SECONDS = _env_int("ACCOUNT_REQUEST_THROTTLE_SECONDS", 300)
PORTAL_AUTH_RECOVERY_THROTTLE_SECONDS = _env_int(
    "PORTAL_AUTH_RECOVERY_THROTTLE_SECONDS",
    300,
)
SHIPMENT_TRACKING_ACCESS_LOGIN_THROTTLE_SECONDS = _env_int(
    "SHIPMENT_TRACKING_ACCESS_LOGIN_THROTTLE_SECONDS",
    60,
)
SHIPMENT_TRACKING_ACCESS_RECOVERY_THROTTLE_SECONDS = _env_int(
    "SHIPMENT_TRACKING_ACCESS_RECOVERY_THROTTLE_SECONDS",
    300,
)
SHIPMENT_TRACKING_ACCESS_GRANT_TTL_DAYS = _env_int(
    "SHIPMENT_TRACKING_ACCESS_GRANT_TTL_DAYS",
    180,
)
PUBLIC_ORDER_THROTTLE_SECONDS = _env_int("PUBLIC_ORDER_THROTTLE_SECONDS", 300)
EMAIL_QUEUE_MAX_ATTEMPTS = _env_int("EMAIL_QUEUE_MAX_ATTEMPTS", 5)
EMAIL_QUEUE_RETRY_BASE_SECONDS = _env_int("EMAIL_QUEUE_RETRY_BASE_SECONDS", 60)
EMAIL_QUEUE_RETRY_MAX_SECONDS = _env_int("EMAIL_QUEUE_RETRY_MAX_SECONDS", 3600)
EMAIL_QUEUE_PROCESSING_TIMEOUT_SECONDS = _env_int("EMAIL_QUEUE_PROCESSING_TIMEOUT_SECONDS", 900)
ENABLE_SHIPMENT_TRACK_LEGACY = _env_bool("ENABLE_SHIPMENT_TRACK_LEGACY", False)
