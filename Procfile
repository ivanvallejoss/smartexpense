web: gunicorn --chdir backend config.wsgi:application --log-file -
worker: cd backend && celery -A config worker --loglevel=info