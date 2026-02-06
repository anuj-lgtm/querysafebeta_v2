import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'querySafe v0.1.settings')

app = Celery('querySafe')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()