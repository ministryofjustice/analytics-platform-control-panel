# Third-party
from django.contrib import messages
from rules.contrib.views import PermissionRequiredMixin

# First-party/Local
from controlpanel.oidc import OIDCLoginRequiredMixin


class PolicyAccessMixin(OIDCLoginRequiredMixin, PermissionRequiredMixin):
    """
    Updates policy access for a model instance.
    Assumes updating a boolean field and updating a policy based on it.
    Must set success_message and method_name attributes on view.
    """

    http_method_names = ["post"]
    permission_required = "api.add_superuser"
    success_message = ""
    method_name = ""

    def form_valid(self, form):
        if not hasattr(self.object, self.method_name):
            raise AttributeError(f"Method {self.method_name} not found on {self.object}")

        getattr(self.object, self.method_name)()
        return super().form_valid(form)

    def get_success_url(self):
        messages.success(self.request, self.success_message)
        return super().get_success_url()
