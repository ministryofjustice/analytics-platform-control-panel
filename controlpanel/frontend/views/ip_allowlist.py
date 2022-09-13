from django.contrib import messages
from django.urls import reverse_lazy
from django.views.generic.list import ListView
from django.views.generic.edit import CreateView, UpdateView, DeleteView
from rules.contrib.views import PermissionRequiredMixin
from django.http.response import HttpResponseRedirect

from controlpanel.api.models import IPAllowlist
from controlpanel.frontend.forms import IPAllowlistForm
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


class IPAllowlistCreate(OIDCLoginRequiredMixin, PermissionRequiredMixin, CreateView):
    """
    Create a new allowlist of IP networks
    """
    form_class = IPAllowlistForm
    context_object_name = 'ip_allowlist'
    model = IPAllowlist
    permission_required = "api.create_ip_allowlist"
    template_name = "ip-allowlist-create.html"

    def form_valid(self, form):
        """
        Ensure the object is created as expected
        """
        self.object = form.save()
        messages.success(self.request, "Successfully created new IP allowlist")
        return HttpResponseRedirect(reverse_lazy("list-ip-allowlists"))

class IPAllowlistDetail(OIDCLoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    """
    Displays and allows editing of an IP allowlist
    """
    form_class = IPAllowlistForm
    context_object_name = 'ip_allowlist'
    model = IPAllowlist
    permission_required = 'api.update_ip_allowlist'
    template_name = "ip-allowlist-detail.html"

    def form_valid(self, form):
        """
        Ensure the object is updated as expected
        """
        self.object = form.save()
        messages.success(self.request, "Successfully updated IP allowlist")
        return HttpResponseRedirect(reverse_lazy("list-ip-allowlists"))

class IPAllowlistDelete(OIDCLoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    """
    Delete an IP allowlist
    """
    model = IPAllowlist
    permission_required = 'api.destroy_ip_allowlist'

    def get_success_url(self):
        messages.success(self.request, "Successfully deleted IP allowlist")
        return reverse_lazy("list-ip-allowlists")
