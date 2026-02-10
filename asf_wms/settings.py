import os
import sys
from pathlib import Path

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


SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-secret-key-change-this")

DEBUG = _env_bool("DJANGO_DEBUG", True)

ALLOWED_HOSTS: list[str] = _env_list("DJANGO_ALLOWED_HOSTS")
SITE_BASE_URL = os.environ.get("SITE_BASE_URL", "").strip()

SECURE_SSL_REDIRECT = _env_bool("SECURE_SSL_REDIRECT", not DEBUG)
SESSION_COOKIE_SECURE = _env_bool("SESSION_COOKIE_SECURE", not DEBUG)
CSRF_COOKIE_SECURE = _env_bool("CSRF_COOKIE_SECURE", not DEBUG)
SECURE_HSTS_SECONDS = int(
    os.environ.get("SECURE_HSTS_SECONDS", "0" if DEBUG else "31536000")
)
SECURE_HSTS_INCLUDE_SUBDOMAINS = _env_bool(
    "SECURE_HSTS_INCLUDE_SUBDOMAINS", not DEBUG
)
SECURE_HSTS_PRELOAD = _env_bool("SECURE_HSTS_PRELOAD", not DEBUG)
SECURE_CONTENT_TYPE_NOSNIFF = _env_bool("SECURE_CONTENT_TYPE_NOSNIFF", True)
X_FRAME_OPTIONS = os.environ.get("X_FRAME_OPTIONS", "DENY")
SECURE_REFERRER_POLICY = os.environ.get(
    "SECURE_REFERRER_POLICY", "same-origin"
)
CSRF_TRUSTED_ORIGINS = _env_list("CSRF_TRUSTED_ORIGINS")
if _env_bool("USE_PROXY_SSL_HEADER", not DEBUG):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

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
    "django.contrib.sessions.middleware.SessionMiddleware",
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
            ],
        },
    },
]

WSGI_APPLICATION = "asf_wms.wsgi.application"

RUNNING_TESTS = "test" in sys.argv
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
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

LANGUAGE_CODE = "fr-fr"
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

EMAIL_BACKEND = os.environ.get(
    "EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend"
)
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "no-reply@example.com")
EMAIL_HOST = os.environ.get("EMAIL_HOST", "")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = _env_bool("EMAIL_USE_TLS", True)
EMAIL_USE_SSL = _env_bool("EMAIL_USE_SSL", False)
BREVO_API_KEY = os.environ.get("BREVO_API_KEY", "")
BREVO_SENDER_EMAIL = os.environ.get("BREVO_SENDER_EMAIL", "")
BREVO_SENDER_NAME = os.environ.get("BREVO_SENDER_NAME", "")
BREVO_REPLY_TO_EMAIL = os.environ.get("BREVO_REPLY_TO_EMAIL", "")

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

ENABLE_BASIC_AUTH = _env_bool("ENABLE_BASIC_AUTH", DEBUG)
_default_authentication_classes = [
    "rest_framework.authentication.SessionAuthentication",
]
if ENABLE_BASIC_AUTH:
    _default_authentication_classes.append(
        "rest_framework.authentication.BasicAuthentication"
    )

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": tuple(_default_authentication_classes),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
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
ACCOUNT_REQUEST_THROTTLE_SECONDS = _env_int("ACCOUNT_REQUEST_THROTTLE_SECONDS", 300)
EMAIL_QUEUE_MAX_ATTEMPTS = _env_int("EMAIL_QUEUE_MAX_ATTEMPTS", 5)
EMAIL_QUEUE_RETRY_BASE_SECONDS = _env_int("EMAIL_QUEUE_RETRY_BASE_SECONDS", 60)
EMAIL_QUEUE_RETRY_MAX_SECONDS = _env_int("EMAIL_QUEUE_RETRY_MAX_SECONDS", 3600)
EMAIL_QUEUE_PROCESSING_TIMEOUT_SECONDS = _env_int(
    "EMAIL_QUEUE_PROCESSING_TIMEOUT_SECONDS", 900
)
