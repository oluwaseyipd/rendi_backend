"""
rendi_backend/settings/production.py
--------------------------------------
Production settings — deployed environment.

Usage:
  Set in your hosting environment:
  DJANGO_SETTINGS_MODULE=rendi_backend.settings.production

Required environment variables (set in your hosting dashboard):
  SECRET_KEY, DB_URL, REDIS_URL, SENDGRID_API_KEY,
  ALLOWED_HOSTS, CORS_ALLOWED_ORIGINS, FRONTEND_URL,
  DEFAULT_FROM_EMAIL, EMAIL_FROM_NAME
"""

from .base import *  # noqa: F401, F403
import dj_database_url
from decouple import config

# ------------------------------------------------------------------
# Security
# ------------------------------------------------------------------
SECRET_KEY = config("SECRET_KEY")
DEBUG = False
ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="").split(",")

# ------------------------------------------------------------------
# Database — PostgreSQL via DATABASE_URL
# ------------------------------------------------------------------
DATABASES = {
    "default": dj_database_url.config(
        default=config("DB_URL"),
        conn_max_age=600,
        ssl_require=True,
    )
}

# ------------------------------------------------------------------
# CORS
# ------------------------------------------------------------------
CORS_ALLOWED_ORIGINS = config(
    "CORS_ALLOWED_ORIGINS", default=""
).split(",")

# ------------------------------------------------------------------
# Security hardening
# ------------------------------------------------------------------
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = "DENY"

# ------------------------------------------------------------------
# Email — SendGrid (configured in base.py, key comes from env)
# ------------------------------------------------------------------
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"

# ------------------------------------------------------------------
# Celery — Redis broker (Upstash, Railway Redis, etc.)
# ------------------------------------------------------------------
CELERY_BROKER_URL = config("REDIS_URL")
CELERY_RESULT_BACKEND = config("REDIS_URL")

# ------------------------------------------------------------------
# Logging
# ------------------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "apps": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}