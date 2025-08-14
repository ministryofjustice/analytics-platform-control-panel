# Third-party
from django.conf import settings
from django.views.generic.base import TemplateView

# First-party/Local
from controlpanel.api.models.user import User  # noqa: F401


class LoginFail(TemplateView):
    ERROR_USE_GITHUB = "use_github"

    template_name = "login-fail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["environment"] = settings.ENV
        context["auth0_logout_url"] = settings.AUTH0["logout_url"]
        context["show_github_login_prompt"] = self.request.GET.get("error") == self.ERROR_USE_GITHUB
        return context
