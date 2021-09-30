from django.conf import settings
from django.views.generic.base import TemplateView


class LoginFail(TemplateView):
    template_name = "login-fail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["environment"] = settings.ENV 
        context["EKS"] = settings.EKS
        return context
