from django.conf import settings
from django.views.generic.base import TemplateView
from controlpanel.api.models.user import User


class LoginFail(TemplateView):
    template_name = "login-fail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["environment"] = settings.ENV 
        context["auth0_logout_url"] = settings.AUTH0["logout_url"]

        return context
