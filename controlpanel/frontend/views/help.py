# Third-party
from django.views.generic.base import TemplateView

# First-party/Local
from controlpanel.oidc import OIDCLoginRequiredMixin


class Help(OIDCLoginRequiredMixin, TemplateView):
    template_name = "help.html"
