from django.views.generic.list import ListView
from rules.contrib.views import PermissionRequiredMixin

from controlpanel.api.models import IPAllowlist
from controlpanel.oidc import OIDCLoginRequiredMixin


class IPAllowlistList(OIDCLoginRequiredMixin, PermissionRequiredMixin, ListView):
    """
    Used to display a list of all IP Allowlists.
    """
    context_object_name = 'ip_allowlists'
    model = IPAllowlist
    permission_required = 'api.list_ip_allowlists'
    queryset = IPAllowlist.objects.all()
    template_name = "ip-allowlist-list.html"
    ordering = ["name"]
