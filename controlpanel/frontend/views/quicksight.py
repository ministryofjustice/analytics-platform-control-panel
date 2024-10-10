# Standard library
from typing import Any

# Third-party
from django.views.generic import TemplateView

# First-party/Local
from controlpanel.api.aws import AWSQuicksight
from controlpanel.oidc import OIDCLoginRequiredMixin


class QuicksightView(OIDCLoginRequiredMixin, TemplateView):
    template_name = "quicksight/index.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["embed_url"] = AWSQuicksight().get_embed_url(user=self.request.user)
        return context
