# Standard library
import os
from pathlib import Path

# Third-party
import dotenv
import structlog
from celery import Celery
from django.conf import settings
from kombu import Queue

# First-party/Local
from controlpanel.utils import load_app_conf_from_file

dotenv.load_dotenv()


# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'controlpanel.settings')
load_app_conf_from_file()

app = Celery('controlpanel')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object('django.conf:settings')
# Load task modules from all registered Django apps.
app.autodiscover_tasks()

log = structlog.getLogger(__name__)


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')


@app.task(bind=True, ignore_result=True)
def worker_health_check(self):
    Path(settings.WORKER_HEALTH_FILENAME).touch()
    log.debug("Worker health ping task executed")


# ensures worker picks and runs tasks from all queues rather than just default queue
# alternative is to run the worker and pass queue name to -Q flag
app.conf.task_queues = [
    Queue(settings.IAM_QUEUE_NAME, routing_key=settings.IAM_QUEUE_NAME),
    Queue(settings.AUTH_QUEUE_NAME, routing_key=settings.AUTH_QUEUE_NAME),
    Queue(settings.S3_QUEUE_NAME, routing_key=settings.S3_QUEUE_NAME),
]
app.conf.task_default_exchange = "tasks"
