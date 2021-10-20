from django.conf import settings
from django.views.generic.base import TemplateView
from controlpanel.api.models.user import User


class LoginFail(TemplateView):
    template_name = "login-fail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["environment"] = settings.ENV 
        context["EKS"] = settings.EKS
        is_migrated = self.request.user.migration_state == User.COMPLETE
        # This flag denotes the user has migrated but is trying to log into the
        # old infrastructure. Used in the template to point them in the right
        # direction. ;-)
        context["in_wrong_place"] = is_migrated and not settings.EKS
        return context
