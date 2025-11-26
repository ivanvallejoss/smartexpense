"""
Configuracoin de Celery para SmartExpense
"""
import os

from celery import Celery

# Set default Django settings
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("smartexpense")

# Load config from Django settings (usa el prefijo CELERY_)
app.config_from_object("django.conf:settings", namespace="CELERY")

# Auto-discover tasks in all apps (busca tasks.py en cada app)
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Task de debug para verificar que Celery funciona"""
    print(f"Request: {self.request!r}")
