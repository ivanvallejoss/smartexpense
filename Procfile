web: gunicorn --chdir backend config.wsgi:application --log-file -
worker: celery -A config worker --loglevel=info