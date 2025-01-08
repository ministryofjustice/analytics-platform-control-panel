# Standard library
from typing import Any

# Third-party
import structlog
from django.conf import settings
from django.views.generic import TemplateView
from rules.contrib.views import PermissionRequiredMixin

# First-party/Local
from controlpanel.api.aws import AWSQuicksight
from controlpanel.oidc import OIDCLoginRequiredMixin

log = structlog.getLogger(__name__)


class QuicksightView(OIDCLoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    template_name = "quicksight.html"

    def has_permission(self):
        user = self.request.user
        return user.has_perm("api.quicksight_embed_author_access") or user.has_perm(
            "api.quicksight_embed_reader_access"
        )

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        profile_name = f"quicksight_user_{self.request.user.justice_email}"
        assume_role_name = settings.QUICKSIGHT_ASSUMED_ROLE
        quicksight_region = settings.QUICKSIGHT_ACCOUNT_REGION
        context["broadcast_messages"] = None
        quicksight_client = AWSQuicksight(
            assume_role_name=assume_role_name,
            profile_name=profile_name,
            region_name=quicksight_region,
        )

        log.info(
            f"client.assume_role_name: {quicksight_client.assume_role_name}, \
            client.region_name: {quicksight_client.region_name}, \
            client.profile_name: {quicksight_client.profile_name}"
        )

        context["embed_url"] = quicksight_client.get_embed_url(user=self.request.user)
        return context
