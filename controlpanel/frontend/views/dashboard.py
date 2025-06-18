# Third-party
import sentry_sdk
import structlog
from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.template.defaultfilters import pluralize
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views.generic.base import RedirectView
from django.views.generic.detail import DetailView, SingleObjectMixin
from django.views.generic.edit import CreateView, DeleteView, FormView
from django.views.generic.list import ListView
from rules.contrib.views import PermissionRequiredMixin

# First-party/Local
from controlpanel.api.exceptions import DeleteCustomerError
from controlpanel.api.models import Dashboard, DashboardDomain, DashboardViewer, User
from controlpanel.frontend.forms import (
    AddCustomersForm,
    GrantDomainAccessForm,
    RegisterDashboardForm,
    RemoveCustomerByEmailForm,
)
from controlpanel.oidc import OIDCLoginRequiredMixin
from controlpanel.utils import feature_flag_required

log = structlog.getLogger(__name__)


@method_decorator(feature_flag_required("register_dashboard"), name="dispatch")
class DashboardList(OIDCLoginRequiredMixin, PermissionRequiredMixin, ListView):
    context_object_name = "dashboards"
    model = Dashboard
    template_name = "dashboard-list.html"

    def has_permission(self):
        return self.request.user.is_quicksight_user()

    def get_queryset(self):
        return self.request.user.dashboards.all()


@method_decorator(feature_flag_required("register_dashboard"), name="dispatch")
class AdminDashboardList(DashboardList):
    template_name = "dashboard-admin-list.html"

    def has_permission(self):
        return self.request.user.is_superuser

    def get_queryset(self):
        return Dashboard.objects.all().prefetch_related("admins")


@method_decorator(feature_flag_required("register_dashboard"), name="dispatch")
class RegisterDashboard(OIDCLoginRequiredMixin, PermissionRequiredMixin, CreateView):
    form_class = RegisterDashboardForm
    model = Dashboard
    template_name = "dashboard-register.html"

    def has_permission(self):
        return self.request.user.is_quicksight_user()

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get_success_url(self):
        messages.success(
            self.request,
            f"Successfully registered {self.object.name} dashboard",
        )
        return reverse_lazy("manage-dashboard", kwargs={"pk": self.object.pk})

    def form_valid(self, form):
        # add dashboard, set creator as an admin and viewer
        with transaction.atomic():
            user = self.request.user
            email = user.justice_email.lower()
            dashboard = form.save(commit=False)
            dashboard.created_by = user
            dashboard.save()
            dashboard.admins.add(user)
            viewer, created = DashboardViewer.objects.get_or_create(email=email)
            dashboard.viewers.add(viewer)
            self.object = dashboard
            return HttpResponseRedirect(self.get_success_url())


@method_decorator(feature_flag_required("register_dashboard"), name="dispatch")
class DashboardDetail(OIDCLoginRequiredMixin, PermissionRequiredMixin, DetailView):
    context_object_name = "dashboard"
    model = Dashboard
    permission_required = "api.retrieve_dashboard"
    template_name = "dashboard-detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        dashboard = self.get_object()
        dashboard_admins = dashboard.admins.all()

        potential_admins = User.objects.exclude(
            auth0_id="",
        ).exclude(
            auth0_id__in=[user.auth0_id for user in dashboard_admins],
        )

        context["admin_options"] = [user for user in potential_admins if user.is_quicksight_user()]

        context["dashboard_admins"] = dashboard_admins

        context["grant_access_form"] = GrantDomainAccessForm(
            dashboard=dashboard,
        )

        return context


@method_decorator(feature_flag_required("register_dashboard"), name="dispatch")
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


class UpdateDashboardBaseView(
    OIDCLoginRequiredMixin,
    PermissionRequiredMixin,
    SingleObjectMixin,
    RedirectView,
):
    http_method_names = ["post"]
    model = Dashboard

    def perform_update(self):
        raise NotImplementedError("Subclasses must define this method")

    def get_redirect_url(self, *args, **kwargs):
        return reverse_lazy("manage-dashboard", kwargs={"pk": kwargs["pk"]})

    def post(self, request, *args, **kwargs):
        self.perform_update(**kwargs)
        return super().post(request, *args, **kwargs)


@method_decorator(feature_flag_required("register_dashboard"), name="dispatch")
class AddDashboardAdmin(UpdateDashboardBaseView):
    permission_required = "api.add_dashboard_admin"

    def perform_update(self, **kwargs):
        dashboard = self.get_object()

        user_id = self.request.POST.get("user_id")
        if not user_id:
            messages.error(self.request, "User not found")
            return
        try:
            user = User.objects.get(pk=self.request.POST["user_id"])
        except User.DoesNotExist:
            messages.error(self.request, "User not found")
            return

        if user.is_quicksight_user():
            dashboard.admins.add(user)
            dashboard.add_customers([user.justice_email], self.request.user.justice_email)
            messages.success(self.request, f"Granted admin access to {user.name}")
            log.info(
                f"{self.request.user.justice_email} granted admin access to {user.justice_email}"
            )
            return

        messages.error(self.request, "User cannot be added as a dashboard admin")


@method_decorator(feature_flag_required("register_dashboard"), name="dispatch")
class RevokeDashboardAdmin(UpdateDashboardBaseView):
    permission_required = "api.revoke_dashboard_admin"

    def perform_update(self, **kwargs):
        dashboard = self.get_object()
        user = get_object_or_404(User, pk=kwargs["user_id"])

        dashboard.admins.remove(user)
        log.info(
            f"{self.request.user.justice_email} removed admin access from {user.justice_email}"
        )
        messages.success(self.request, f"Removed admin access from {user.name}")


@method_decorator(feature_flag_required("register_dashboard"), name="dispatch")
class DashboardCustomers(OIDCLoginRequiredMixin, PermissionRequiredMixin, DetailView):
    context_object_name = "dashboard"
    model = Dashboard
    permission_required = "api.retrieve_dashboard"
    template_name = "dashboard-user-list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        dashboard = self.get_object()

        customers = dashboard.viewers.all()
        paginator = Paginator(customers, 50)

        context["errors"] = self.request.session.pop("customer_form_errors", None)
        context["page_no"] = page_no = self.kwargs.get("page_no")
        context["paginator"] = paginator
        context["elided"] = paginator.get_elided_page_range(page_no)
        context["customers"] = customers
        context["remove_customer_form"] = RemoveCustomerByEmailForm()
        return context


@method_decorator(feature_flag_required("register_dashboard"), name="dispatch")
class AddDashboardCustomers(
    OIDCLoginRequiredMixin, PermissionRequiredMixin, SingleObjectMixin, FormView
):
    model = Dashboard
    form_class = AddCustomersForm
    permission_required = "api.add_dashboard_customer"

    def form_invalid(self, form):
        self.request.session["customer_form_errors"] = form.errors
        messages.error(self.request, "Could not add user(s)")
        return HttpResponseRedirect(self.get_success_url())

    def form_valid(self, form):
        dashboard = self.get_object()
        emails = form.cleaned_data["customer_email"]
        not_notified = dashboard.add_customers(emails, self.request.user.justice_email)
        log.info(
            f"{self.request.user.justice_email} granted {', '.join(emails)} "
            f"access to dashboard {dashboard.name}"
        )
        messages.success(self.request, "Successfully added users")

        if len(not_notified) > 0:
            messages.error(
                self.request,
                (
                    f"Failed to notify {', '.join(not_notified)}. "
                    "You may wish to email them your dashboard link."
                ),
            )
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self, *args, **kwargs):
        return reverse_lazy("dashboard-customers", kwargs={"pk": self.kwargs["pk"], "page_no": 1})


@method_decorator(feature_flag_required("register_dashboard"), name="dispatch")
class RemoveDashboardCustomerById(UpdateDashboardBaseView):
    permission_required = "api.remove_dashboard_customer"

    def get_redirect_url(self, *args, **kwargs):
        return reverse_lazy("dashboard-customers", kwargs={"pk": self.kwargs["pk"], "page_no": 1})

    def perform_update(self, **kwargs):
        dashboard = self.get_object()
        user_ids = self.request.POST.getlist("customer")
        try:
            dashboard.delete_customers_by_id(user_ids)
        except DeleteCustomerError as e:
            sentry_sdk.capture_exception(e)
            messages.error(self.request, f"Failed removing user{pluralize(user_ids)}")
        else:
            messages.success(self.request, f"Successfully removed user{pluralize(user_ids)}")
            log.info(
                f"{self.request.user.justice_email} removing {pluralize(user_ids)} "
                f"access to dashboard {dashboard.name}"
            )


@method_decorator(feature_flag_required("register_dashboard"), name="dispatch")
class RemoveDashboardCustomerByEmail(UpdateDashboardBaseView):
    form = None
    permission_required = "api.remove_dashboard_customer"

    def get_redirect_url(self, *args, **kwargs):
        return reverse_lazy("dashboard-customers", kwargs={"pk": self.kwargs["pk"], "page_no": 1})

    def perform_update(self, **kwargs):
        """
        Attempts to remove a user from a group, based on their email address
        """
        self.form = RemoveCustomerByEmailForm(data=self.request.POST)
        if not self.form.is_valid():
            self.request.session["customer_form_errors"] = self.form.errors
            return messages.error(self.request, "Invalid email address entered")

        dashboard = self.get_object()
        email = self.form.cleaned_data["email"]
        try:
            dashboard.delete_customer_by_email(email)
        except DeleteCustomerError as e:
            sentry_sdk.capture_exception(e)
            return messages.error(
                self.request, str(e) or f"Couldn't remove user with email {email}"
            )

        messages.success(self.request, f"Successfully removed user {email}")
        log.info(
            f"{self.request.user.justice_email} removing {email} access to dashboard {dashboard.name}"
        )


@method_decorator(feature_flag_required("register_dashboard"), name="dispatch")
class GrantDomainAccess(
    OIDCLoginRequiredMixin,
    PermissionRequiredMixin,
    SingleObjectMixin,
    FormView,
):
    form_class = GrantDomainAccessForm
    model = Dashboard
    permission_required = "api.add_dashboard_domain"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        if "dashboard" not in kwargs:
            kwargs["dashboard"] = Dashboard.objects.get(pk=self.kwargs["pk"])
        return kwargs

    def get_success_url(self):
        return reverse_lazy("manage-dashboard", kwargs={"pk": self.kwargs["pk"]})

    def form_valid(self, form):
        domain = form.cleaned_data["whitelist_domain"]
        dashboard = self.get_object()
        dashboard.whitelist_domains.add(domain)
        messages.success(self.request, f"Successfully granted access to {domain.name}")
        log.info(
            f"{self.request.user.justice_email} granting {domain.name} "
            f"wide access for dashboard {dashboard.name}"
        )
        return super().form_valid(form)

    def form_invalid(self, form):
        log.warning("Received suspicious invalid grant app access request")
        raise Exception(form.errors)


@method_decorator(feature_flag_required("register_dashboard"), name="dispatch")
class RevokeDomainAccess(UpdateDashboardBaseView):
    permission_required = "api.remove_dashboard_domain"

    def perform_update(self, **kwargs):
        dashboard = self.get_object()
        domain = DashboardDomain.objects.get(pk=kwargs["domain_id"])
        dashboard.whitelist_domains.remove(domain)
        log.info(
            f"{self.request.user.justice_email} revoking {domain.name} wide access for dashboard {dashboard.name}"
        )
        messages.success(self.request, f"Successfully removed {domain.name}")
