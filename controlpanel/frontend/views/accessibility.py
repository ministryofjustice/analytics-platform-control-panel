# Third-party
from django.conf import settings  # noqa: F401
from django.views.generic.base import TemplateView

# First-party/Local
from controlpanel.oidc import OIDCLoginRequiredMixin


class Accessibility(OIDCLoginRequiredMixin, TemplateView):
    template_name = "a11y.html"
