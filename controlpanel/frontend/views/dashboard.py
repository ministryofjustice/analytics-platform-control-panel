# Third-party
import structlog
from django.contrib import messages
from django.db import transaction
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.utils.html import format_html
from django.views.generic.base import RedirectView, TemplateView
from django.views.generic.detail import DetailView, SingleObjectMixin
from django.views.generic.edit import CreateView, DeleteView, FormView, UpdateView
from django.views.generic.list import ListView
from rules.contrib.views import PermissionRequiredMixin

# First-party/Local
from controlpanel import utils
from controlpanel.api import aws
from controlpanel.api.models import (
    Dashboard,
    DashboardAdminAccess,
    DashboardDomain,
    DashboardDomainAccess,
    DashboardViewer,
    DashboardViewerAccess,
)
from controlpanel.frontend.forms import (
    AddDashboardAdminForm,
    AddDashboardViewersForm,
    GrantDomainAccessForm,
    RegisterDashboardForm,
    UpdateDashboardForm,
)
from controlpanel.oidc import OIDCLoginRequiredMixin
from controlpanel.utils import build_success_message

log = structlog.getLogger(__name__)


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


class AdminDashboardList(DashboardList):
    template_name = "dashboard-admin-list.html"

    def has_permission(self):
        return self.request.user.is_superuser

    def get_queryset(self):
        return Dashboard.objects.all().prefetch_related("admins")


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

            dashboard = Dashboard.objects.create(
                name=preview_data["name"],
                description=preview_data.get("description", ""),
                quicksight_id=preview_data["quicksight_id"],
                created_by=user,
            )
            dashboard.admin_access.create(user=user, added_by=user)
            if preview_data.get("whitelist_domain"):
                DashboardDomainAccess.objects.create(
                    dashboard=dashboard,
                    domain=DashboardDomain.objects.get(name=preview_data.get("whitelist_domain")),
                    added_by=user,
                )

            # Add any additional viewers from the emails list
            not_notified = dashboard.add_viewers(preview_data.get("emails", []), user)
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


class CancelDashboardRegistration(OIDCLoginRequiredMixin, RedirectView):
    url = reverse_lazy("list-dashboards")

    def get(self, request, *args, **kwargs):
        request.session.pop("dashboard_preview", None)
        return super().get(request, *args, **kwargs)


class DashboardDetail(OIDCLoginRequiredMixin, PermissionRequiredMixin, DetailView):
    context_object_name = "dashboard"
    model = Dashboard
    permission_required = "api.retrieve_dashboard"
    template_name = "dashboard-detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        dashboard = self.get_object()
        context["success_message"] = self.request.session.pop("success_message", None)

        context["dashboard_admins"] = dashboard.admin_access.select_related("user", "added_by")
        context["num_admins"] = len(context["dashboard_admins"])
        context["dashboard_viewers"] = dashboard.viewer_access.select_related("viewer", "shared_by")
        context["num_viewers"] = len(context["dashboard_viewers"])
        context["domain_whitelist"] = dashboard.domain_access.select_related("domain", "added_by")
        context["num_domains"] = len(context["domain_whitelist"])
        context["show_add_domain_button"] = context["num_domains"] < DashboardDomain.objects.count()
        context["embed_url"] = aws.AWSQuicksight().get_dashboard_embed_url(
            user=self.request.user,
            dashboard_id=dashboard.quicksight_id,
        )

        return context


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
        kwargs["request"] = self.request
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["dashboard"] = self.dashboard
        return context

    def form_valid(self, form):
        new_admins = form.save()

        for user in new_admins:
            log.info(
                f"{self.request.user.justice_email} granted {self.dashboard.name} admin access to {user.justice_email}",  # noqa
                audit="dashboard_audit",
            )

        self.request.session["success_message"] = {
            "heading": f"You have updated admin rights for {self.dashboard.name}",
            "message": None,
        }

        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return f"{self.dashboard.get_absolute_url()}#admins"


class RevokeDashboardAdmin(OIDCLoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    permission_required = "api.revoke_dashboard_admin"
    model = DashboardAdminAccess
    template_name = "dashboard-admin-remove-confirm.html"

    def get_success_url(self):
        res = self.object.dashboard.get_absolute_url()
        return f"{res}#admins"

    def get_object(self, queryset=None):
        dashboard = get_object_or_404(Dashboard, pk=self.kwargs["pk"])
        if not dashboard.admins.count() > 1:
            raise Http404("Dashboard has no admins that can be revoked")

        return get_object_or_404(
            dashboard.admin_access.select_related("dashboard", "user"),
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

        try:
            dashboard.delete_admin(user=user, admin=self.request.user)
        except utils.GovukNotifyEmailError:
            messages.error(
                self.request,
                (
                    f"Failed to notify {user.justice_email}. "
                    "You may wish to email them to let them know their admin access has been removed."  # noqa
                ),
            )

        self.request.session["success_message"] = build_success_message(
            heading=f"You have updated admin rights for {dashboard.name}", message=None
        )

        log.info(
            f"{self.request.user.justice_email} removing {user.justice_email} "
            f"admin from dashboard {dashboard.name}",
            audit="dashboard_audit",
        )

        return HttpResponseRedirect(self.get_success_url())


class RevokeDashboardViewer(OIDCLoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    permission_required = "api.revoke_dashboard_viewer"
    model = DashboardViewerAccess
    template_name = "dashboard-viewer-remove-confirm.html"

    def get_success_url(self):
        res = self.object.dashboard.get_absolute_url()
        return f"{res}#viewers"

    def get_object(self, queryset=None):
        return get_object_or_404(
            DashboardViewerAccess.objects.select_related("dashboard", "viewer"),
            dashboard__pk=self.kwargs["pk"],
            viewer__pk=self.kwargs["viewer_id"],
        )

    def get_permission_object(self):
        return self.get_object().dashboard

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["viewer"] = self.get_object().viewer
        context["dashboard"] = self.get_object().dashboard
        return context

    def form_valid(self, form):
        self.object = self.get_object()
        dashboard = self.object.dashboard
        viewer = self.object.viewer

        try:
            dashboard.delete_viewers([viewer], admin=self.request.user)
        except utils.GovukNotifyEmailError:
            messages.error(
                self.request,
                (
                    f"Failed to notify {viewer.email}. "
                    "You may wish to email them to let them know their viewer access has been removed."  # noqa
                ),
            )

        self.request.session["success_message"] = build_success_message(
            heading=f"You have removed viewers from {dashboard.name}", message=None
        )

        log.info(
            f"{self.request.user.justice_email} removing {viewer.email} "
            f"viewer access from dashboard {dashboard.name}",
            audit="dashboard_audit",
        )

        return HttpResponseRedirect(self.get_success_url())


class AddDashboardViewers(OIDCLoginRequiredMixin, PermissionRequiredMixin, FormView):
    permission_required = "api.add_dashboard_viewer"
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
            "heading": f"You've shared {self.dashboard.name}",
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
