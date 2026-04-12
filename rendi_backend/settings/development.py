"""
rendi_backend/settings/development.py
---------------------------------------
Local development settings.

Usage:
  export DJANGO_SETTINGS_MODULE=rendi_backend.settings.development
  python manage.py runserver

Or set in .env:
  DJANGO_SETTINGS_MODULE=rendi_backend.settings.development
"""

from .base import *  # noqa: F401, F403
from decouple import config

# ------------------------------------------------------------------
# Security
# ------------------------------------------------------------------
SECRET_KEY = config("SECRET_KEY", default="dev-insecure-secret-key-change-in-prod")
DEBUG = True
ALLOWED_HOSTS = ["localhost", "127.0.0.1"]

# ------------------------------------------------------------------
# Database — SQLite for local dev (zero setup)
# ------------------------------------------------------------------
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",  # noqa: F405
    }
}

# Uncomment to use local PostgreSQL instead:
# DATABASES = {
#     "default": {
#         "ENGINE": "django.db.backends.postgresql",
#         "NAME": config("DB_NAME", default="rendi_db"),
#         "USER": config("DB_USER", default="rendi_user"),
#         "PASSWORD": config("DB_PASSWORD", default=""),
#         "HOST": config("DB_HOST", default="localhost"),
#         "PORT": config("DB_PORT", default="5432"),
#     }
# }

# ------------------------------------------------------------------
# CORS — allow local Next.js dev server
# ------------------------------------------------------------------
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

# ------------------------------------------------------------------
# Email — print to console in development (no SendGrid needed)
# ------------------------------------------------------------------
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# ------------------------------------------------------------------
# Celery — use in-memory broker for local dev (no Redis needed)
# Switch to Redis URL when you want to test real async tasks locally.
# ------------------------------------------------------------------
CELERY_TASK_ALWAYS_EAGER = True          # tasks run synchronously
CELERY_TASK_EAGER_PROPAGATES = True      # exceptions surface immediately
CELERY_BROKER_URL = config("REDIS_URL", default="memory://")
CELERY_RESULT_BACKEND = "cache+memory://"

# ------------------------------------------------------------------
# Django debug toolbar (optional — install django-debug-toolbar if wanted)
# ------------------------------------------------------------------
# INSTALLED_APPS += ["debug_toolbar"]
# MIDDLEWARE += ["debug_toolbar.middleware.DebugToolbarMiddleware"]