web: cd && gunicorn config.wsgi --log-file -
worker cd && celery -A config worker --log-level=info
