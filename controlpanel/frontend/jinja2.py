# Standard library
import os

# Third-party
import jinja2
from django.conf import settings
from django.contrib import messages
from django.templatetags.static import static
from django.urls import reverse
from django.utils.timesince import timesince


def environment(**kwargs):
    env = jinja2.Environment(**kwargs)
    env.globals.update(
        {
            "env": os.environ.get("ENV", "dev"),
            "get_messages": messages.get_messages,
            "timesince": timesince,
            "static": static,
            "url": reverse,
            "google_analytics_id": settings.GOOGLE_ANALYTICS_ID,
            "dashboard_url": settings.DASHBOARD_SERVICE_URL,
            "user_guidance_base_url": settings.USER_GUIDANCE_BASE_URL,
        }
    )
    return env
