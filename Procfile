web: gunicorn rendi_backend.wsgi:application
worker: celery -A rendi_backend worker --loglevel=info
beat: celery -A rendi_backend beat --loglevel=info