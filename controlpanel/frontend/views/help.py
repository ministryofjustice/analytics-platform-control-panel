from django.views.generic.base import TemplateView

from controlpanel.oidc import OIDCLoginRequiredMixin


class Help(OIDCLoginRequiredMixin, TemplateView):
    template_name = "help.html"
