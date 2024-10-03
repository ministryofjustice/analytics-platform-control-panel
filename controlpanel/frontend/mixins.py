# Third-party
from django.contrib import messages
from rules.contrib.views import PermissionRequiredMixin

# First-party/Local
from controlpanel.oidc import OIDCLoginRequiredMixin


class BedrockAccessMixin(OIDCLoginRequiredMixin, PermissionRequiredMixin):
    """Updates bedrock access for a given model instance."""

    fields = ["is_bedrock_enabled"]
    http_method_names = ["post"]
    permission_required = "api.add_superuser"

    def form_valid(self, form):
        self.object.set_bedrock_access()
        return super().form_valid(form)

    def get_success_url(self):
        messages.success(self.request, "Successfully updated bedrock status")
        return super().get_success_url()


class TextractAccessMixin(OIDCLoginRequiredMixin, PermissionRequiredMixin):
    """Updates textract access for a given model instance."""

    fields = ["is_textract_enabled"]
    http_method_names = ["post"]
    permission_required = "api.add_superuser"

    def form_valid(self, form):
        self.object.set_textract_access()
        return super().form_valid(form)

    def get_success_url(self):
        messages.success(self.request, "Successfully updated textract status")
        return super().get_success_url()
