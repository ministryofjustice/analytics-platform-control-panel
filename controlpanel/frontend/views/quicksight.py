# Standard library
from typing import Any

# Third-party
from django.conf import settings
from django.views.generic import TemplateView
from rules.contrib.views import PermissionRequiredMixin

# First-party/Local
from controlpanel.api.aws import AWSQuicksight
from controlpanel.oidc import OIDCLoginRequiredMixin


class QuicksightView(OIDCLoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    template_name = "quicksight.html"
    permission_required = "is_superuser"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        profile_name = f"quicksight_user_{self.request.user.justice_email}"

        context["embed_url"] = AWSQuicksight(
            assume_role_name=settings.QUICKSIGHT_ASSUMED_ROLE,
            profile_name=profile_name,
            region_name=settings.QUICKSIGHT_ACCOUNT_REGION,
        ).get_embed_url(user=self.request.user)
        return context
