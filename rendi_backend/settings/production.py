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


# -----------------------------------------------------------------
#  PyMySQL setup to allow using MySQL with Django's MySQLdb backend
# -----------------------------------------------------------------
import pymysql

pymysql.version_info = (2, 2, 8, "final", 0)  # Manually spoof the version to satisfy Django
pymysql.install_as_MySQLdb()

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
        # SSL is handled differently in MySQL; 
        # many shared cPanel hosts don't support enforced SSL for remote DBs 
        # unless specifically configured. Start with False if you get errors.
        ssl_require=False, 
    )
}

# Ensure MySQL works correctly with Django
DATABASES["default"]["OPTIONS"] = {
    'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
    'charset': 'utf8mb4',
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