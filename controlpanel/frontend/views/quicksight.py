# Standard library
from typing import Any

# Third-party
import botocore
import sentry_sdk
import structlog
from django.conf import settings
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.urls import reverse_lazy
from django.views.generic import FormView, TemplateView
from rules.contrib.views import PermissionRequiredMixin

# First-party/Local
from controlpanel.api.aws import AWSQuicksight
from controlpanel.frontend.forms import QuicksightFolderForm
from controlpanel.oidc import OIDCLoginRequiredMixin

log = structlog.getLogger(__name__)


def _create_quicksight_client(user):
    profile_name = f"quicksight_user_{user.justice_email}"
    assume_role_name = settings.QUICKSIGHT_ASSUMED_ROLE
    quicksight_region = settings.QUICKSIGHT_ACCOUNT_REGION
    return AWSQuicksight(
        assume_role_name=assume_role_name,
        profile_name=profile_name,
        region_name=quicksight_region,
    )


class QuicksightView(OIDCLoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    template_name = "quicksight.html"

    def has_permission(self):
        user = self.request.user
        return user.is_quicksight_user()

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["broadcast_messages"] = None
        context["display_service_info"] = False
        quicksight_client = _create_quicksight_client(self.request.user)

        log.info(
            f"client.assume_role_name: {quicksight_client.assume_role_name}, \
            client.region_name: {quicksight_client.region_name}, \
            client.profile_name: {quicksight_client.profile_name}"
        )

        context["embed_url"] = quicksight_client.get_embed_url(user=self.request.user)
        return context


class QuicksightCreateFolderView(OIDCLoginRequiredMixin, PermissionRequiredMixin, FormView):
    template_name = "quicksight-create-folder.html"
    form_class = QuicksightFolderForm

    def has_permission(self):
        user = self.request.user
        return user.is_quicksight_author()

    def form_valid(self, form):
        try:
            folder_id = form.cleaned_data["folder_id"]
            quicksight_client = _create_quicksight_client(self.request.user)
            quicksight_client.create_folder(
                user=self.request.user,
                folder_id=folder_id,
            )
            messages.success(self.request, "Successfully created shared folder")
        except botocore.exceptions.ClientError as error:

            if error.response["Error"]["Code"] == "ResourceExistsException":
                messages.error(self.request, f"Folder with name {folder_id} already exists")
                return HttpResponseRedirect(reverse_lazy("quicksight-create-folder"))

        return HttpResponseRedirect(reverse_lazy("quicksight"))

    def form_invalid(self, form):
        messages.error(self.request, "Failed to create shared folder")
        return HttpResponseRedirect(reverse_lazy("quicksight-create-folder"))
