import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'chrisr.settings')

app = Celery('luciane')

app.config_from_object('django.conf:settings', namespace='CELERY')
app.loader.override_backends['django-db'] = 'django_celery_results.backends.database:DatabaseBackend'
app.autodiscover_tasks()