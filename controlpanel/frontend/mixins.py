# Third-party
from django.contrib import messages
from rules.contrib.views import PermissionRequiredMixin

# First-party/Local
from controlpanel.oidc import OIDCLoginRequiredMixin


class PolicyAccessMixin(OIDCLoginRequiredMixin, PermissionRequiredMixin):
    """Updates policy access for a model instance. Assumes updating a boolean field and updating a policy based on it."""

    http_method_names = ["post"]
    permission_required = "api.add_superuser"
    success_message = ""
    method_name = ""

    def form_valid(self, form):

        try:
            if not hasattr(self.object, self.method_name):
                raise AttributeError(f"Method {self.method_name} not found on {self.object}")

            getattr(self.object, self.method_name)()
            return super().form_valid(form)
        except Exception as e:
            messages.error(self.request, "An error occurred while updating the policy access level")
            return super().form_invalid(form)

    def get_success_url(self):
        messages.success(self.request, self.success_message)
        return super().get_success_url()
