import os

from celery import Celery

import dotenv
import django


app = Celery('controlpanels')

dotenv.load_dotenv()

# TODO update
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'controlpanel.settings.development')

from controlpanel.utils import load_app_conf_from_file
load_app_conf_from_file()

django.setup()
# Load task modules from all registered Django app configs.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks in all installed applications
app.autodiscover_tasks(["controlpanel.frontend", "controlpanel.api"])

# define in settings?
# app.conf.broker_url = 'redis://localhost:6379/0'

@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
