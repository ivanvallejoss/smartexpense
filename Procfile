web: cd backend && gunicorn config.wsgi --log-file -
worker cd backend && celery -A config worker --log-level=info
