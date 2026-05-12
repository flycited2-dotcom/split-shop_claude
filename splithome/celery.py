import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'splithome.settings.local')

app = Celery('splithome')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
