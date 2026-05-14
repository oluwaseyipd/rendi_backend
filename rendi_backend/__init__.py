# Intentionally empty.
#
# We do NOT auto-import Celery here because it causes a race condition
# on startup — the celery.py module sets DJANGO_SETTINGS_MODULE to
# 'production' before manage.py can set it to 'development'.
#
# The Celery app is loaded automatically by the Celery worker process
# itself (via -A rendi_backend). For Django management commands and
# runserver, no Celery import is needed at startup.

# import pymysql
# pymysql.install_as_MySQLdb()
