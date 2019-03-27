from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic.base import TemplateView
import requests


class WhatsNew(LoginRequiredMixin, TemplateView):
    template_name = "whats-new.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        response = requests.get(settings.WHATS_NEW_URL)
        response.raise_for_status()

        context["markdown_body"] = response.text
        return context
