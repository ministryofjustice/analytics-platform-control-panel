# Third-party
import sentry_sdk
import structlog
from django.conf import settings
from django.contrib import messages
from django.db import transaction
from django.db.models import Prefetch
from django.http import HttpResponse, HttpResponseRedirect
from django.urls import reverse_lazy
from django.utils.http import urlencode
from django.views.generic.base import View
from django.views.generic.detail import DetailView
from django.views.generic.edit import CreateView, DeleteView, FormMixin, UpdateView
from django.views.generic.list import ListView
from rules.contrib.views import PermissionRequiredMixin

# First-party/Local
from controlpanel.api.models import Dashboard, DashboardDomain, DashboardViewer, User
from controlpanel.frontend.forms import RegisterDashboardForm
from controlpanel.oidc import OIDCLoginRequiredMixin

log = structlog.getLogger(__name__)


class DashboardList(OIDCLoginRequiredMixin, PermissionRequiredMixin, ListView):
    context_object_name = "dashboards"
    model = Dashboard
    permission_required = "api.list_dashboard"
    template_name = "dashboard-list.html"

    def get_queryset(self):
        return self.request.user.dashboards.all()


class AdminDashboardList(DashboardList):
    permission_required = "api.is_superuser"
    template_name = "dashboard-admin-list.html"

    def get_queryset(self):
        return Dashboard.objects.all().prefetch_related("admins")


class RegisterDashboard(OIDCLoginRequiredMixin, PermissionRequiredMixin, CreateView):
    form_class = RegisterDashboardForm
    model = Dashboard
    permission_required = "api.register_dashboard"
    template_name = "dashboard-register.html"

    def get_success_url(self):
        messages.success(
            self.request,
            f"Successfully registered {self.object.name} dashboard",
        )
        return reverse_lazy("list-dashboards")
        # return reverse_lazy("manage-dashboard", kwargs={"pk": self.object.pk})

    def form_valid(self, form):
        # add dashboard, set creator as an admin and viewer
        with transaction.atomic():
            user = self.request.user
            dashboard = form.save()
            dashboard.created_by = user
            dashboard.admins.add(user)
            viewer, created = DashboardViewer.objects.get_or_create(email=user.justice_email)
            dashboard.viewers.add(viewer)
            dashboard.save()
            self.object = dashboard
            return HttpResponseRedirect(self.get_success_url())


class DashboardDetail(OIDCLoginRequiredMixin, PermissionRequiredMixin, DetailView):
    context_object_name = "dashboard"
    model = Dashboard
    permission_required = "api.retrieve_dashboard"
    template_name = "dashboard-detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        dashboard = self.get_object()

        context["admin_options"] = User.objects.exclude(
            auth0_id="",
        ).exclude(
            auth0_id__in=[user.auth0_id for user in dashboard.admins],
        )

        return context


class DeleteDashboard(OIDCLoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = Dashboard
    permission_required = "api.destroy_dashboard"
    success_url = reverse_lazy("list-dashboards")
    allowed_methods = ["POST"]

    def form_valid(self, form):
        dashboard = self.get_object()
        dashboard.delete()
        messages.success(self.request, f"Successfully deleted {dashboard.name} dashboard")
        return HttpResponseRedirect(self.get_success_url())


class AddDashboardCustomers(OIDCLoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    # Quite possibly some many-to-many relationship
    model = "<model_here>"
    form_class = "<form_here>"
    permission_required = "api.add_dashboard_customer"

    def form_invalid(self, form):
        self.request.session["add_customer_form_errors"] = form.errors
        return HttpResponseRedirect(self.get_success_url())

    def form_valid(self, form):
        # Add to the many-to-many relationship
        messages.success(self.request, "Successfully added customers")
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self, *args, **kwargs):
        pass


class RemoveDashboardCustomer(OIDCLoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = "<model_here>"
    form_class = "<form_here>"
    permission_required = "api.remove_dashboard_customer"

    def form_invalid(self, form):
        self.request.session["remove_customer_form_errors"] = form.errors
        return HttpResponseRedirect(self.get_success_url())

    def form_valid(self, form):
        # Remove from the many-to-many relationship
        messages.success(self.request, "Successfully removed customers")
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self, *args, **kwargs):
        pass


class AddDashboardAdmin(OIDCLoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = "<model_here>"
    form_class = "<form_here>"
    permission_required = "api.add_dashboard_admin"


class RevokeAdmin(OIDCLoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = "<model_here>"
    form_class = "<form_here>"
    permission_required = "api.revoke_dashboard_admin"
