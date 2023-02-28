# Third-party
from django.contrib import messages
from django.urls import reverse_lazy
from django.http import HttpResponseRedirect
from django.views.generic.edit import CreateView, DeleteView, UpdateView, FormMixin
from django.views.generic.list import ListView
from rules.contrib.views import PermissionRequiredMixin

# First-party/Local
from controlpanel.api.models import IPAllowlist
from controlpanel.api.models.apps_mng import AppManager
from controlpanel.frontend.forms import IPAllowlistForm
from controlpanel.oidc import OIDCLoginRequiredMixin


class IPAllowlistList(OIDCLoginRequiredMixin, PermissionRequiredMixin, ListView):
    """
    Used to display a list of all IP Allowlists.
    """

    context_object_name = "ip_allowlists"
    model = IPAllowlist
    permission_required = "api.list_ip_allowlists"
    queryset = IPAllowlist.objects.all()
    template_name = "ip-allowlist-list.html"
    ordering = ["name"]


class IPAllowlistCreate(OIDCLoginRequiredMixin, PermissionRequiredMixin, CreateView):
    """
    Create a new allowlist of IP networks
    """

    form_class = IPAllowlistForm
    context_object_name = "ip_allowlist"
    model = IPAllowlist
    permission_required = "api.create_ip_allowlist"
    template_name = "ip-allowlist-create.html"

    def get_success_url(self):
        messages.success(self.request, "Successfully created new IP allowlist")
        return reverse_lazy("list-ip-allowlists")


class IPAllowlistDetail(OIDCLoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    """
    Displays and allows editing of an IP allowlist
    """

    form_class = IPAllowlistForm
    context_object_name = "ip_allowlist"
    model = IPAllowlist
    permission_required = "api.update_ip_allowlist"
    template_name = "ip-allowlist-detail.html"

    def get_success_url(self):
        messages.success(self.request, "Successfully updated IP allowlist")
        return reverse_lazy("list-ip-allowlists")

    def form_valid(self, form):
        pre_update_object = self.get_object()
        updated_object = form.save()
        # Trigger the task for updating the related apps' ip_ranges
        AppManager().trigger_tasks_for_ip_range_update(self.request.user, pre_update_object, updated_object)
        return HttpResponseRedirect(self.get_success_url())


class IPAllowlistDelete(OIDCLoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    """
    Delete an IP allowlist
    """

    model = IPAllowlist
    permission_required = "api.destroy_ip_allowlist"

    def get_success_url(self):
        messages.success(self.request, "Successfully deleted IP allowlist")
        return reverse_lazy("list-ip-allowlists")

    def form_valid(self, form):
        ip_allowlist = self.get_object()
        ip_allowlist.deleted=True
        ip_allowlist.save()
        # Trigger the task for updating the related apps' ip_ranges
        AppManager().trigger_tasks_for_ip_range_removal(self.request.user, ip_allowlist)
        return HttpResponseRedirect(self.get_success_url())
