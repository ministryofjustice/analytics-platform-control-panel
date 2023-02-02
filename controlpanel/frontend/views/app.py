# Standard library
from typing import List

# Third-party
import sentry_sdk
import structlog
from django.conf import settings
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.template.defaultfilters import pluralize
from django.urls import reverse, reverse_lazy
from django.views.generic.base import RedirectView
from django.views.generic.detail import DetailView, SingleObjectMixin
from django.views.generic.edit import CreateView, DeleteView, FormMixin, UpdateView
from django.views.generic.list import ListView
from rules.contrib.views import PermissionRequiredMixin

# First-party/Local
from controlpanel.api import auth0, cluster
from controlpanel.api.models import (
    App,
    AppS3Bucket,
    IPAllowlist,
    S3Bucket,
    User,
    UserApp,
    UserS3Bucket,
)
from controlpanel.api.pagination import Auth0Paginator
from controlpanel.frontend.forms import (
    AddAppCustomersForm,
    CreateAppForm,
    GrantAppAccessForm,
    UpdateAppAuth0ConnectionsForm,
)
from controlpanel.frontend.views import secrets
from controlpanel.oidc import OIDCLoginRequiredMixin

log = structlog.getLogger(__name__)


class AppList(OIDCLoginRequiredMixin, PermissionRequiredMixin, ListView):
    context_object_name = "apps"
    model = App
    permission_required = "api.list_app"
    template_name = "webapp-list.html"

    def get_queryset(self):
        qs = App.objects.all().prefetch_related("userapps")
        return qs.filter(userapps__user=self.request.user)


class AdminAppList(AppList):
    permission_required = "api.is_superuser"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["all_webapps"] = True
        return context

    def get_queryset(self):
        return App.objects.all().prefetch_related("userapps")


class AppDetail(OIDCLoginRequiredMixin, PermissionRequiredMixin, DetailView):
    context_object_name = "app"
    model = App
    permission_required = "api.retrieve_app"
    template_name = "webapp-detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        app = self.get_object()

        # Log data consistency warnings. (Missing Auth0 ID).
        for user in app.admins:
            if not user.auth0_id:
                log.warning(
                    "User without Auth0 ID, {}, is admin for app: {}.".format(user, app)
                )

        # TODO: Fix this.
        # THIS IS A TEMPORARY STICKING PLASTER
        # During migration to EKS, just use the hard coded domain with the
        # app's SLUG as the bottom subdomain.
        # The reason for this change is apps will be hosted on our
        # old infrastructure while users migrate to EKS. Once we have our
        # app hosting story figured out, we should do this properly.
        context["apps_on_eks"] = settings.features.apps_on_eks.enabled
        context["app_url"] = f"https://{ app.slug }.{settings.APP_DOMAIN}"
        context["app_ip_allowlists_names"] = ", ".join(
            list(app.ip_allowlists.values_list("name", flat=True))
        )

        if settings.features.apps_on_eks.enabled:
            context["app_url"] = cluster.App(app).url

        context["admin_options"] = (
            User.objects.filter(
                auth0_id__isnull=False,
            )
            .exclude(
                auth0_id="",
            )
            .exclude(
                auth0_id__in=[user.auth0_id for user in app.admins],
            )
        )

        context["grant_access_form"] = GrantAppAccessForm(
            app=app,
            exclude_connected=True,
        )

        add_customer_form_errors = self.request.session.pop(
            "add_customer_form_errors", None
        )
        if add_customer_form_errors:
            errors = context.setdefault("errors", {})
            errors["customer_email"] = add_customer_form_errors["customer_email"]

        set_secrets = cluster.App(self.object).get_secret_if_found()

        context["kibana_base_url"] = settings.KIBANA_BASE_URL
        context[
            "has_setup_completed_for_client"
        ] = auth0.ExtendedAuth0().has_setup_completed_for_client(app.slug)
        context["allowed_secret_keys"] = {
            key: set_secrets.get(key) for key, _ in secrets.ALLOWED_SECRETS.items()
        }

        context["feature_enabled"] = settings.features.app_migration.enabled
        context["parameters"] = (
            cluster.App(app).set_secret_type("parameters").get_secret_if_found()
        )
        return context


class CreateApp(OIDCLoginRequiredMixin, PermissionRequiredMixin, CreateView):
    form_class = CreateAppForm
    model = App
    permission_required = "api.create_app"
    template_name = "webapp-create.html"

    def get_form_kwargs(self):
        kwargs = FormMixin.get_form_kwargs(self)
        kwargs.update(
            request=self.request,
            all_connections_names=auth0.ExtendedAuth0().connections.get_all_connection_names(),  # noqa: E501
            custom_connections=auth0.ExtendedConnections.custom_connections(),
        )
        return kwargs

    def get_success_url(self):
        messages.success(
            self.request,
            f"Successfully registered {self.object.name} webapp",
        )
        return reverse_lazy("list-apps")

    def _create_or_link_datasource(self, form):
        if form.cleaned_data.get("new_datasource_name"):
            bucket = S3Bucket.objects.create(
                name=form.cleaned_data["new_datasource_name"], bucket_owner="APP"
            )
            AppS3Bucket.objects.create(
                app=self.object,
                s3bucket=bucket,
                access_level="readonly",
            )
            UserS3Bucket.objects.create(
                user=self.request.user,
                s3bucket=bucket,
                access_level="readwrite",
                is_admin=True,
            )
        elif form.cleaned_data.get("existing_datasource_id"):
            AppS3Bucket.objects.create(
                app=self.object,
                s3bucket=form.cleaned_data["existing_datasource_id"],
                access_level="readonly",
            )

    def _register_app(self, form, name, repo_url, ip_allowlists):
        self.object = App.objects.create(
            name=name,
            repo_url=repo_url,
        )

        self.object.ip_allowlists.add(*ip_allowlists)

        self._create_or_link_datasource(form)

        UserApp.objects.create(
            app=self.object,
            user=self.request.user,
            is_admin=True,
        )

        client = auth0.ExtendedAuth0().setup_auth0_client(
            self.object.slug, connections=form.cleaned_data.get("auth0_connections")
        )

        secret_data: dict = {
            **self.object.construct_secret_data(client),
            "disable_authentication": form.cleaned_data.pop(
                "disable_authentication", False
            ),
        }
        cluster.App(self.object).create_or_update_secret(secret_data)

    def form_valid(self, form):
        repo_url = form.cleaned_data["repo_url"]
        ip_allowlists = form.cleaned_data["app_ip_allowlists"]

        _, name = repo_url.rsplit("/", 1)
        try:
            self._register_app(form, name, repo_url, ip_allowlists)
        except Exception as ex:
            form.add_error("repo_url", str(ex))
            return FormMixin.form_invalid(self, form)
        return FormMixin.form_valid(self, form)


class UpdateAppAuth0Connections(
    OIDCLoginRequiredMixin, PermissionRequiredMixin, UpdateView
):

    form_class = UpdateAppAuth0ConnectionsForm
    model = App
    permission_required = "api.create_app"
    template_name = "webapp-auth0-connections-update.html"
    success_url = "manage-app"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context

    def get_form_kwargs(self):
        kwargs = FormMixin.get_form_kwargs(self)
        app = self.get_object()
        kwargs.update(
            request=self.request,
            all_connections_names=auth0.ExtendedAuth0().connections.get_all_connection_names(),  # noqa: E501
            custom_connections=auth0.ExtendedConnections.custom_connections(),
            auth0_connections=app.auth0_connections,
        )
        return kwargs

    def get_success_url(self):
        messages.success(
            self.request,
            f"Successfully updated {self.object.name} webapp's auth0 connections",
        )
        return reverse_lazy("manage-app", kwargs={"pk": self.object.id})

    def form_valid(self, form):
        try:
            auth0.ExtendedAuth0().update_client_auth_connections(
                self.object.slug,
                new_conns=form.cleaned_data.get("auth0_connections"),
                existing_conns=form.auth0_connections,
            )
        except Exception as ex:
            form.add_error("connections", str(ex))
            return FormMixin.form_invalid(self, form)
        return FormMixin.form_valid(self, form)


class UpdateAppIPAllowlists(
    OIDCLoginRequiredMixin, PermissionRequiredMixin, UpdateView
):

    model = App
    template_name = "webapp-update-ip-allowlists.html"
    permission_required = "api.update_app_ip_allowlists"
    fields = ["ip_allowlists"]

    def get_context_data(self, *args, **kwargs):

        context = super().get_context_data(*args, **kwargs)
        context["app"] = self.get_object()
        context[
            "app_migration_feature_enabled"
        ] = settings.features.app_migration.enabled
        context["app_ip_allowlists"] = [
            {
                "text": ip_allowlist.name,
                "value": ip_allowlist.pk,
                "checked": ip_allowlist in self.get_object().ip_allowlists.all(),
            }
            for ip_allowlist in IPAllowlist.objects.all()
        ]

        return context

    def form_valid(self, form):
        """
        Update the App's list of IPAllowlists, which will trigger the App's entry in
        AWS Secrets Manager to be updated (see signal app_ip_allowlists_changed() in
        App model).
        """

        app = self.get_object()
        app.ip_allowlists.set(form.cleaned_data["ip_allowlists"])

        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        messages.success(
            self.request,
            f"Successfully updated the IP allowlists associated with app {self.get_object().name}",  # noqa:E501
        )
        return reverse_lazy("manage-app", kwargs={"pk": self.get_object().id})


class GrantAppAccess(
    OIDCLoginRequiredMixin,
    PermissionRequiredMixin,
    CreateView,
):
    form_class = GrantAppAccessForm
    model = AppS3Bucket
    permission_required = "api.add_app_bucket"

    def get_form_kwargs(self):
        kwargs = FormMixin.get_form_kwargs(self)
        if "app" not in kwargs:
            kwargs["app"] = App.objects.get(pk=self.kwargs["pk"])
        return kwargs

    def get_success_url(self):
        messages.success(self.request, "Successfully granted access")
        return reverse_lazy("manage-app", kwargs={"pk": self.object.app.id})

    def form_valid(self, form):
        # TODO this can be replaced with AppS3Bucket.objects.get_or_create()
        try:
            self.object = AppS3Bucket.objects.get(
                s3bucket=form.cleaned_data["datasource"],
                app_id=self.kwargs["pk"],
            )
            self.object.access_level = form.cleaned_data["access_level"]
            self.object.save()
        except AppS3Bucket.DoesNotExist:
            self.object = AppS3Bucket.objects.create(
                access_level=form.cleaned_data["access_level"],
                app_id=self.kwargs["pk"],
                s3bucket=form.cleaned_data["datasource"],
            )
        return FormMixin.form_valid(self, form)

    def form_invalid(self, form):
        # It should be impossible to get here. The form consists of
        # ChoiceFields, so the only way an invalid input can be submitted is by
        # constructing the request manually - in which (suspicious) case we should
        # return as little information as possible
        log.warning("Received suspicious invalid grant app access request")
        raise Exception(form.errors)


class RevokeAppAccess(OIDCLoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = AppS3Bucket
    permission_required = "api.remove_app_bucket"

    def get_success_url(self):
        messages.success(self.request, "Successfully disconnected data source")
        return reverse_lazy("manage-app", kwargs={"pk": self.object.app.id})


class UpdateAppAccess(OIDCLoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = AppS3Bucket
    permission_required = "api.update_apps3bucket"
    fields = ["access_level"]

    def get_success_url(self):
        messages.success(self.request, "Successfully updated access")
        if self.request.POST.get("return_to") == "manage-datasource":
            return reverse_lazy(
                "manage-datasource", kwargs={"pk": self.object.s3bucket.id}
            )
        return reverse_lazy("manage-app", kwargs={"pk": self.object.app.id})


class DeleteApp(OIDCLoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = App
    permission_required = "api.destroy_app"
    success_url = reverse_lazy("list-apps")

    def delete(self, request, *args, **kwargs):
        app = self.get_object()
        messages.success(self.request, f"Successfully deleted {app.name} app")
        return super().delete(request, *args, **kwargs)


class UpdateApp(
    OIDCLoginRequiredMixin,
    PermissionRequiredMixin,
    SingleObjectMixin,
    RedirectView,
):
    http_method_names = ["post"]
    model = App

    def get_redirect_url(self, *args, **kwargs):
        return reverse_lazy("manage-app", kwargs={"pk": kwargs["pk"]})

    def post(self, request, *args, **kwargs):
        self.perform_update(**kwargs)
        return super().post(request, *args, **kwargs)


class SetupAppAuth0(
    OIDCLoginRequiredMixin,
    PermissionRequiredMixin,
    SingleObjectMixin,
    RedirectView,
):
    http_method_names = ["post"]
    permission_required = "api.setup_app_auth0"
    model = App

    def get_redirect_url(self, *args, **kwargs):
        return reverse_lazy("manage-app", kwargs={"pk": kwargs["pk"]})

    def post(self, request, *args, **kwargs):
        app = self.get_object()
        auth0.ExtendedAuth0().setup_auth0_client(app_name=app.slug)
        return super().post(request, *args, **kwargs)


class ResetAppSecret(
    OIDCLoginRequiredMixin,
    PermissionRequiredMixin,
    SingleObjectMixin,
    RedirectView,
):
    http_method_names = ["post"]
    permission_required = "api.setup_app_auth0"
    model = App

    def get_redirect_url(self, *args, **kwargs):
        return reverse_lazy("manage-app", kwargs={"pk": kwargs["pk"]})

    def post(self, request, *args, **kwargs):
        app = self.get_object()
        client = auth0.ExtendedAuth0().clients.search_first_match(dict(name=app.slug))
        if client:
            cluster.App(app).create_or_update_secret(app.construct_secret_data(client))
        return super().post(request, *args, **kwargs)


class AddCustomers(OIDCLoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    form_class = AddAppCustomersForm
    model = App
    permission_required = "api.add_app_customer"

    def form_invalid(self, form):
        self.request.session["add_customer_form_errors"] = form.errors
        return HttpResponseRedirect(
            reverse_lazy("manage-app", kwargs={"pk": self.kwargs["pk"]}),
        )

    def form_valid(self, form):
        self.get_object().add_customers(form.cleaned_data["customer_email"])
        return HttpResponseRedirect(self.get_success_url())

    def get_form_kwargs(self):
        kwargs = FormMixin.get_form_kwargs(self)
        return kwargs

    def get_success_url(self, *args, **kwargs):
        messages.success(self.request, "Successfully added customers")
        return reverse_lazy(
            "appcustomers-page", kwargs={"pk": self.kwargs["pk"], "page_no": 1}
        )


class AppCustomersPageView(OIDCLoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = App
    permission_required = "api.retrieve_app"
    template_name = "customers-list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        app: App = context.get("app")

        group_id = self.request.GET.get("group_id") or app.get_group_id()
        context["group_id"] = group_id
        context["page_no"] = page_no = self.kwargs.get("page_no")
        customers = app.customer_paginated(page_no, group_id)

        context["customers"] = customers.get("users", [])
        context["paginator"] = paginator = self._paginate_customers(customers)
        context["elided"] = paginator.get_elided_page_range(page_no)
        return context

    def _paginate_customers(self, auth_results: List[dict], per_page=25):
        total_count = auth_results.get("total", 0)
        customer_result = auth_results.get("users", [])
        paginator = Auth0Paginator(
            customer_result, per_page=per_page, total_count=total_count
        )
        return paginator


class RemoveCustomer(UpdateApp):
    permission_required = "api.remove_app_customer"

    def get_redirect_url(self, *args, **kwargs):
        return reverse(
            "appcustomers-page", kwargs={"pk": self.kwargs["pk"], "page_no": 1}
        )

    def perform_update(self, **kwargs):
        app = self.get_object()
        user_ids = self.request.POST.getlist("customer")
        try:
            app.delete_customers(user_ids)
        except App.DeleteCustomerError as e:
            sentry_sdk.capture_exception(e)
            messages.error(
                self.request, f"Failed removing customer{pluralize(user_ids)}"
            )
        else:
            messages.success(
                self.request, f"Successfully removed customer{pluralize(user_ids)}"
            )


class AddAdmin(UpdateApp):
    permission_required = "api.add_app_admin"

    def perform_update(self, **kwargs):
        app = self.get_object()
        user = get_object_or_404(User, pk=self.request.POST["user_id"])
        if user.auth0_id:
            userapp = UserApp.objects.create(
                app=app,
                user=user,
                is_admin=True,
            )
            userapp.save()
            messages.success(self.request, f"Granted admin access to {user.name}")
        else:
            messages.error(
                self.request,
                f"Failed to grant admin access to {user.name} because they lack an Auth0 ID.",  # noqa: E501
            )


class RevokeAdmin(UpdateApp):
    permission_required = "api.revoke_app_admin"

    def perform_update(self, **kwargs):
        app = self.get_object()
        user = get_object_or_404(User, pk=kwargs["user_id"])
        userapp = get_object_or_404(UserApp, app=app, user=user)
        userapp.delete()
        messages.success(self.request, f"Revoked admin access for {user.name}")
