# Third-party
from django.views.generic import TemplateView
from rules.contrib.views import PermissionRequiredMixin

# First-party/Local
from controlpanel.oidc import OIDCLoginRequiredMixin


class DatabasesListView(
    OIDCLoginRequiredMixin,
    PermissionRequiredMixin,
    TemplateView,
):
    template_name = "databases-list.html"
    permission_required = "api.is_superuser"
