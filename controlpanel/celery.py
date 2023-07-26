import os
import dotenv

from celery import Celery

from controlpanel.utils import load_app_conf_from_file

dotenv.load_dotenv()
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "controlpanel.settings")
load_app_conf_from_file()

app = Celery('controlpanel')

# Load task modules from all registered Django app configs.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks in all installed applications
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
