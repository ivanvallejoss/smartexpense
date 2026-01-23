web: PYTHONPATH=backend gunicorn config.wsgi --log-file -
worker: PYTHONPATH=backend celery -A config worker --log-level=info
