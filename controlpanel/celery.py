import os
import dotenv
from celery import Celery
from time import time
import json

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


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')


@app.task(bind=True)
def create_app_role(self, app_id, user_id):
    from controlpanel.api.models.app import App
    app = App.objects.get(pk=app_id)
    app.description = json.dumps({"app_role": {"task_id": self.request.id, "time": str(int(time()))}})
    app.save()
    from controlpanel.api.models.task import Task
    task = Task.objects.filter(task_id=self.request.id).first()
    if task:
        task.completed = True
        task.save()


@app.task(bind=True)
def create_auth_settings(self, app_id, user_id, deployment_envs, auth_flag, connections, has_ip_ranges):
    from controlpanel.api.models.app import App
    app = App.objects.get(pk=app_id)
    app.description = json.dumps({"app_auth": {"task_id": self.request.id, "time": str(int(time()))}})
    app.save()

    from controlpanel.api.models.task import Task
    task = Task.objects.filter(task_id=self.request.id).first()
    if task:
        task.completed = True
        task.save()


@app.task(bind=True)
def create_s3bucket(self, s3bucket_id, user_id):
    from controlpanel.api.models.s3bucket import S3Bucket
    from controlpanel.api.models.task import Task
    s3bucket = S3Bucket.objects.get(pk=s3bucket_id)
    if s3bucket:
        task = Task.objects.filter(task_id=self.request.id).first()
        if task:
            task.completed = True
            task.save()


@app.task(bind=True)
def s3bucket_grant_to_user(self, users3bucket_id, user_id):
    from controlpanel.api.models.users3bucket import UserS3Bucket
    from controlpanel.api.models.task import Task
    s3bucket = UserS3Bucket.objects.get(pk=users3bucket_id)
    if s3bucket:
        task = Task.objects.filter(task_id=self.request.id).first()
        if task:
            task.completed = True
            task.save()


@app.task(bind=True)
def s3bucket_grant_to_app(self, apps3bucket_id, user_id):
    from controlpanel.api.models.apps3bucket import AppS3Bucket
    from controlpanel.api.models.task import Task
    s3bucket = AppS3Bucket.objects.get(pk=apps3bucket_id)
    if s3bucket:
        task = Task.objects.filter(task_id=self.request.id).first()
        if task:
            task.completed = True
            task.save()


# ensures worker picks and runs tasks from all queues rather than just default queue
# alternative is to run the worker and pass queue name to -Q flag
app.conf.task_queues = [
    Queue("iam_queue"),
    Queue("auth_queue"),
    Queue("s3_queue"),
]
