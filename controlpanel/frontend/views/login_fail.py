from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic.base import TemplateView


class LoginFail(TemplateView):
    template_name = "login-fail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["environment"] = settings.ENV 
        return context
