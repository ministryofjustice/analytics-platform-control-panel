from django.conf import settings
from django.views.generic.base import TemplateView

from controlpanel.oidc import OIDCLoginRequiredMixin


class Accessibility(OIDCLoginRequiredMixin, TemplateView):
    template_name = "a11y.html"
