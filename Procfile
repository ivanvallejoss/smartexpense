web: gunicorn config.wsgi --log-file -
worker celery -A backend/config worker --log-level=info
