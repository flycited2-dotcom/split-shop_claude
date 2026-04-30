import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'oasis.settings.local')

app = Celery('oasis')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
