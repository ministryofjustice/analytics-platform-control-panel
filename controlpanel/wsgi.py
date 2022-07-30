"""
WSGI config for controlpanel project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/2.1/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application
from controlpanel.utils import load_app_conf_from_file

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "controlpanel.settings")

load_app_conf_from_file()

application = get_wsgi_application()
