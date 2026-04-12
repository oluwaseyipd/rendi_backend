"""
rendi_backend/celery.py
------------------------
Celery application configuration for Rendi.

This file is imported by the WSGI/ASGI entry point so that the
@shared_task decorator works across all apps without circular imports.
"""

import os
from celery import Celery

# Default to production settings; manage.py overrides to development
os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    "rendi_backend.settings.development",
)

app = Celery("rendi_backend")

# Read Celery config from Django settings (keys prefixed with CELERY_)
app.config_from_object("django.conf:settings", namespace="CELERY")

# Auto-discover tasks in all INSTALLED_APPS
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f"Request: {self.request!r}")
