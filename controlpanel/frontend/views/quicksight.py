# Standard library
from typing import Any

# Third-party
from django.conf import settings
from django.views.generic import TemplateView

# First-party/Local
from controlpanel.api.aws import AWSQuicksight
from controlpanel.oidc import OIDCLoginRequiredMixin


class QuicksightView(OIDCLoginRequiredMixin, TemplateView):
    template_name = "quicksight.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        assume_role_name = "some_role_name"
        profile_name = "some_profile_name"

        context["embed_url"] = AWSQuicksight(
            assume_role_name=assume_role_name,
            profile_name=profile_name,
            region_name=settings.QUICKSIGHT_ACCOUNT_REGION,
        ).get_embed_url(user=self.request.user)
        return context
