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
from django.utils.html import format_html
from django.views.generic.base import RedirectView, TemplateView
from django.views.generic.detail import DetailView, SingleObjectMixin
from django.views.generic.edit import CreateView, DeleteView, FormView, UpdateView
from django.views.generic.list import ListView
from rules.contrib.views import PermissionRequiredMixin

# First-party/Local
from controlpanel.api import aws
from controlpanel.api.exceptions import DeleteCustomerError
from controlpanel.api.models import (
    Dashboard,
    DashboardAdminAccess,
    DashboardDomain,
    DashboardDomainAccess,
    DashboardViewer,
    DashboardViewerAccess,
    User,
)
from controlpanel.frontend.forms import (
    AddDashboardAdminForm,
    AddDashboardViewersForm,
    GrantDomainAccessForm,
    RegisterDashboardForm,
    RemoveCustomerByEmailForm,
    UpdateDashboardForm,
)
from controlpanel.oidc import OIDCLoginRequiredMixin
from controlpanel.utils import build_success_message, feature_flag_required

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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["success_message"] = self.request.session.pop("success_message", None)
        return context


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

    def get_dashboards(self):
        """Cache dashboards list to avoid multiple API calls"""
        if not hasattr(self, "_dashboards"):
            self._dashboards = aws.AWSQuicksight().get_dashboards_for_user(user=self.request.user)
        return self._dashboards

    def get_initial(self):
        """Pre-populate form with session data if returning from preview."""
        initial = super().get_initial()
        preview_data = self.request.session.get("dashboard_preview")
        if preview_data and preview_data.get("user_id") == self.request.user.id:
            initial["quicksight_id"] = preview_data.get("quicksight_id", "")
            initial["description"] = preview_data.get("description", "")
            initial["emails"] = preview_data.get("emails", [])
        return initial

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        kwargs["dashboards"] = self.get_dashboards()
        return kwargs

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context["dashboards"] = self.get_dashboards()
        return context

    def form_valid(self, form):
        """Store validated form data in session and redirect to preview."""
        self.request.session["dashboard_preview"] = {
            "user_id": self.request.user.id,
            "name": form.cleaned_data["name"],
            "description": form.cleaned_data.get("description", ""),
            "quicksight_id": form.cleaned_data["quicksight_id"],
            "emails": form.cleaned_data.get("emails", []),
            "whitelist_domain": (
                form.cleaned_data.get("whitelist_domain").name
                if form.cleaned_data.get("whitelist_domain")
                else None
            ),
        }
        return HttpResponseRedirect(reverse_lazy("preview-dashboard"))


@method_decorator(feature_flag_required("register_dashboard"), name="dispatch")
class RegisterDashboardPreview(OIDCLoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    template_name = "dashboard-register-preview.html"

    def has_permission(self):
        return self.request.user.is_quicksight_user()

    def get_preview_data(self):
        """Get preview data only if it belongs to the current user."""
        preview_data = self.request.session.get("dashboard_preview")
        if preview_data and preview_data.get("user_id") == self.request.user.id:
            return preview_data
        return None

    def dispatch(self, request, *args, **kwargs):
        if not self.get_preview_data():
            request.session.pop("dashboard_preview", None)
            return HttpResponseRedirect(reverse_lazy("register-dashboard"))
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        preview_data = self.get_preview_data()
        context["preview"] = preview_data

        embed_url = aws.AWSQuicksight().get_dashboard_embed_url(
            user=self.request.user,
            dashboard_id=preview_data["quicksight_id"],
        )
        context["embed_url"] = embed_url

        return context

    def post(self, request, *args, **kwargs):
        """Create the dashboard from session data."""
        preview_data = request.session.pop("dashboard_preview", None)
        if not preview_data:
            return HttpResponseRedirect(reverse_lazy("register-dashboard"))

        if preview_data.get("user_id") != request.user.id:
            return HttpResponseRedirect(reverse_lazy("register-dashboard"))

        with transaction.atomic():
            user = request.user
            email = user.justice_email.lower()

            dashboard = Dashboard.objects.create(
                name=preview_data["name"],
                description=preview_data.get("description", ""),
                quicksight_id=preview_data["quicksight_id"],
                created_by=user,
            )
            dashboard.admins.add(user)
            if preview_data.get("whitelist_domain"):
                DashboardDomainAccess.objects.create(
                    dashboard=dashboard,
                    domain=DashboardDomain.objects.get(name=preview_data.get("whitelist_domain")),
                    added_by=user,
                )

            # Add creator as viewer so they can view it in Dashboard Service
            viewer, _ = DashboardViewer.objects.get_or_create(email=email)
            DashboardViewerAccess.objects.get_or_create(
                dashboard=dashboard,
                viewer=viewer,
                defaults={"shared_by": user},
            )

            # Add any additional viewers from the emails list
            not_notified = dashboard.add_customers(preview_data.get("emails", []), user)
            if not_notified:
                messages.error(
                    request,
                    (
                        f"Failed to notify {', '.join(not_notified)}. "
                        "You may wish to email them your dashboard link."
                    ),
                )

        request.session["success_message"] = build_success_message(
            heading=f"You've shared '{dashboard.name}'",
            message=format_html(
                "To share with more people, or grant admin rights, "
                'go to <a class="govuk-notification-banner__link" href="{}">manage sharing</a>.',
                dashboard.get_absolute_url(),
            ),
        )

        return HttpResponseRedirect(reverse_lazy("list-dashboards"))


@method_decorator(feature_flag_required("register_dashboard"), name="dispatch")
class CancelDashboardRegistration(OIDCLoginRequiredMixin, RedirectView):
    url = reverse_lazy("list-dashboards")

    def get(self, request, *args, **kwargs):
        request.session.pop("dashboard_preview", None)
        return super().get(request, *args, **kwargs)


@method_decorator(feature_flag_required("register_dashboard"), name="dispatch")
class DashboardDetail(OIDCLoginRequiredMixin, PermissionRequiredMixin, DetailView):
    context_object_name = "dashboard"
    model = Dashboard
    permission_required = "api.retrieve_dashboard"
    template_name = "dashboard-detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        dashboard = self.get_object()
        context["success_message"] = self.request.session.pop("success_message", None)

        context["dashboard_admins"] = (
            DashboardAdminAccess.objects.filter(dashboard=dashboard)
            .select_related("user", "added_by")
            .order_by("user__justice_email")
        )
        context["num_admins"] = len(context["dashboard_admins"])
        context["dashboard_viewers"] = (
            DashboardViewerAccess.objects.filter(dashboard=dashboard)
            .select_related("viewer", "shared_by")
            .order_by("viewer__email")
        )
        context["num_viewers"] = len(context["dashboard_viewers"])
        context["domain_whitelist"] = (
            DashboardDomainAccess.objects.filter(dashboard=dashboard)
            .select_related("domain", "added_by")
            .order_by("domain__name")
        )
        context["num_domains"] = len(context["domain_whitelist"])
        context["show_add_domain_button"] = context["num_domains"] < DashboardDomain.objects.count()
        context["embed_url"] = aws.AWSQuicksight().get_dashboard_embed_url(
            user=self.request.user,
            dashboard_id=dashboard.quicksight_id,
        )

        return context


@method_decorator(feature_flag_required("register_dashboard"), name="dispatch")
class DeleteDashboard(OIDCLoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = Dashboard
    permission_required = "api.destroy_dashboard"
    success_url = reverse_lazy("list-dashboards")
    template_name = "dashboard-delete-confirm.html"
    allowed_methods = ["GET", "POST"]

    def form_valid(self, form):
        dashboard = self.get_object()
        dashboard.delete()
        self.request.session["success_message"] = build_success_message(
            heading=f"You've removed {dashboard.name}",
            message="The dashboard will no longer appear in the dashboard service.",
        )

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
        return self.get_object().get_absolute_url()

    def post(self, request, *args, **kwargs):
        self.perform_update(**kwargs)
        return super().post(request, *args, **kwargs)


@method_decorator(feature_flag_required("register_dashboard"), name="dispatch")
class DashboardUpdateDescription(OIDCLoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    context_object_name = "dashboard"
    model = Dashboard
    form_class = UpdateDashboardForm
    permission_required = "api.retrieve_dashboard"
    template_name = "dashboard-update-description.html"

    def form_valid(self, form):
        super().form_valid(form)
        dashboard = self.get_object()
        self.request.session["success_message"] = build_success_message(
            heading=f"You've updated the description for {dashboard.name}", message=None
        )

        return HttpResponseRedirect(self.get_success_url())


@method_decorator(feature_flag_required("register_dashboard"), name="dispatch")
class AddDashboardAdmin(OIDCLoginRequiredMixin, PermissionRequiredMixin, FormView):
    permission_required = "api.add_dashboard_admin"
    template_name = "dashboard-add-admin.html"
    form_class = AddDashboardAdminForm

    def dispatch(self, request, *args, **kwargs):
        self.dashboard = get_object_or_404(Dashboard, pk=kwargs["pk"])
        return super().dispatch(request, *args, **kwargs)

    def get_permission_object(self):
        """Return the dashboard for object-level permission checking."""
        return self.dashboard

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["dashboard"] = self.dashboard
        kwargs["added_by"] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["dashboard"] = self.dashboard
        return context

    def form_valid(self, form):
        dashboard = self.dashboard
        added_users = form.save()
        absolute_url = self.request.build_absolute_uri(dashboard.get_absolute_url())
        dashboard.notify_admin_added(
            new_admins=added_users, admin=self.request.user, manage_url=absolute_url
        )

        emails = [user.justice_email for user in added_users if user.justice_email]
        dashboard.add_customers(emails, self.request.user)

        for user in added_users:
            log.info(
                f"{self.request.user.justice_email} granted admin access to {user.justice_email}",
                audit="dashboard_audit",
            )

        self.request.session["success_message"] = {
            "heading": f"You have updated admin rights for {self.dashboard.name}",
            "message": None,
        }

        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return f"{self.dashboard.get_absolute_url()}#admins"


@method_decorator(feature_flag_required("register_dashboard"), name="dispatch")
class RevokeDashboardAdmin(OIDCLoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    permission_required = "api.revoke_dashboard_admin"
    model = DashboardAdminAccess
    template_name = "dashboard-admin-remove-confirm.html"

    def get_success_url(self):
        res = self.object.dashboard.get_absolute_url()
        return f"{res}#admins"

    def get_object(self, queryset=None):
        return get_object_or_404(
            DashboardAdminAccess.objects.select_related("dashboard", "user"),
            dashboard__pk=self.kwargs["pk"],
            user__pk=self.kwargs["user_id"],
        )

    def get_permission_object(self):
        return self.get_object().dashboard

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["admin"] = self.get_object().user
        context["dashboard"] = self.get_object().dashboard
        return context

    def form_valid(self, form):
        self.object = self.get_object()
        dashboard = self.object.dashboard
        user = self.object.user

        dashboard.delete_admin(user=user, admin=self.request.user)

        self.request.session["success_message"] = build_success_message(
            heading=f"You have updated admin rights for {dashboard.name}", message=None
        )

        log.info(
            f"{self.request.user.justice_email} removing {user.justice_email} "
            f"admin from dashboard {dashboard.name}",
            audit="dashboard_audit",
        )

        return HttpResponseRedirect(self.get_success_url())


# TODO delete view?
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
class AddDashboardCustomers(OIDCLoginRequiredMixin, PermissionRequiredMixin, FormView):
    permission_required = "api.add_dashboard_customer"
    template_name = "dashboard-add-viewers.html"
    form_class = AddDashboardViewersForm

    def dispatch(self, request, *args, **kwargs):
        self.dashboard = get_object_or_404(Dashboard, pk=kwargs["pk"])
        return super().dispatch(request, *args, **kwargs)

    def get_permission_object(self):
        """Return the dashboard for object-level permission checking."""
        return self.dashboard

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["dashboard"] = self.dashboard
        kwargs["shared_by"] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["dashboard"] = self.dashboard
        return context

    def form_valid(self, form):
        emails, not_notified = form.save()

        log.info(
            f"{self.request.user.justice_email} granted {', '.join(emails)} "
            f"access to dashboard {self.dashboard.name}",
            audit="dashboard_audit",
        )

        self.request.session["success_message"] = {
            "heading": f"You have added viewers to {self.dashboard.name}",
            "message": None,
        }

        if not_notified:
            messages.error(
                self.request,
                (
                    f"Failed to notify {', '.join(not_notified)}. "
                    "You may wish to email them your dashboard link."
                ),
            )

        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return f"{self.dashboard.get_absolute_url()}#viewers"


@method_decorator(feature_flag_required("register_dashboard"), name="dispatch")
class RemoveDashboardCustomerById(UpdateDashboardBaseView):
    permission_required = "api.remove_dashboard_customer"

    def get_redirect_url(self, *args, **kwargs):
        return reverse_lazy("dashboard-customers", kwargs={"pk": self.kwargs["pk"], "page_no": 1})

    def perform_update(self, **kwargs):
        dashboard = self.get_object()
        user_ids = self.request.POST.getlist("customer")
        try:
            viewers = dashboard.delete_customers_by_id(user_ids, admin=self.request.user)
            emails = viewers.values_list("email", flat=True)
        except DeleteCustomerError as e:
            sentry_sdk.capture_exception(e)
            messages.error(self.request, f"Failed removing user{pluralize(user_ids)}")
        else:
            messages.success(self.request, f"Successfully removed user{pluralize(emails)}")
            log.info(
                f"{self.request.user.justice_email} removing {', '.join(emails)} "
                f"access to dashboard {dashboard.name}",
                audit="dashboard_audit",
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
            dashboard.delete_customer_by_email(email, admin=self.request.user)
        except DeleteCustomerError as e:
            sentry_sdk.capture_exception(e)
            return messages.error(
                self.request, str(e) or f"Couldn't remove user with email {email}"
            )

        messages.success(self.request, f"Successfully removed user {email}")
        log.info(
            f"{self.request.user.justice_email} removing {email} "
            f"access to dashboard {dashboard.name}",
            audit="dashboard_audit",
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
    template_name = "dashboard-grant-domain-access.html"

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        return super().post(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        if "dashboard" not in kwargs:
            kwargs["dashboard"] = self.object
        return kwargs

    def get_success_url(self):
        return f"{self.object.get_absolute_url()}#domain-access"

    def form_valid(self, form):
        domain = form.cleaned_data["whitelist_domain"]
        dashboard = self.get_object()
        DashboardDomainAccess.objects.create(
            dashboard=dashboard,
            domain=domain,
            added_by=self.request.user,
        )
        self.request.session["success_message"] = build_success_message(
            heading=f"You have updated domain access for {dashboard.name}", message=None
        )

        log.info(
            f"{self.request.user.justice_email} granting {domain.name} "
            f"wide access for dashboard {dashboard.name}",
            audit="dashboard_audit",
        )
        return super().form_valid(form)


@method_decorator(feature_flag_required("register_dashboard"), name="dispatch")
class RevokeDomainAccess(OIDCLoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    permission_required = "api.remove_dashboard_domain"
    model = DashboardDomainAccess
    template_name = "dashboard-domain-remove-confirm.html"

    def get_success_url(self):
        res = self.object.dashboard.get_absolute_url()
        return f"{res}#domain-access"

    def get_object(self, queryset=None):
        return get_object_or_404(
            DashboardDomainAccess.objects.select_related("dashboard", "domain"),
            dashboard__pk=self.kwargs["pk"],
            domain__pk=self.kwargs["domain_id"],
        )

    def get_permission_object(self):
        return self.get_object().dashboard

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["dashboard"] = self.get_object().dashboard
        context["domain"] = self.get_object().domain
        return context

    def form_valid(self, form):
        dashboard = self.object.dashboard
        domain = self.object.domain

        self.request.session["success_message"] = build_success_message(
            heading=f"You have updated domain access for {dashboard.name}", message=None
        )
        log.info(
            f"{self.request.user.justice_email} removing {domain.name} "
            f"domain access to dashboard {dashboard.name}",
            audit="dashboard_audit",
        )

        return super().form_valid(form)
