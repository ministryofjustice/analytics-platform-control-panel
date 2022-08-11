"""
ASGI entrypoint.
Configures Django and then runs the application defined in the ASGI_APPLICATION
setting.
"""

import os
import django
from channels.routing import get_default_application
from controlpanel.utils import load_app_conf_from_file


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "controlpanel.settings")
load_app_conf_from_file()

django.setup()

application = get_default_application()
