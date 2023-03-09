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
    AppIPAllowList,
    AppS3Bucket,
    IPAllowlist,
    User,
    UserApp,
)
from controlpanel.api.pagination import Auth0Paginator
from controlpanel.api.serializers import AppAuthSettingsSerializer
from controlpanel.frontend.forms import (
    AddAppCustomersForm,
    CreateAppForm,
    GrantAppAccessForm,
    UpdateAppAuth0ConnectionsForm,
)
from controlpanel.frontend.views.apps_mng import AppManager
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

    def _get_all_app_settings(self, app):
        app_manager_ins = cluster.App(app)
        deployment_env_names = app_manager_ins.get_deployment_envs(
            self.request.user.github_api_token
        )
        deployments_settings = {}
        for env_name in deployment_env_names:
            deployments_settings[env_name] = {
                "secrets": app_manager_ins.get_env_secrets(
                    self.request.user.github_api_token, env_name=env_name
                ),
                "variables": app_manager_ins.get_env_vars(
                    self.request.user.github_api_token, env_name=env_name
                ),
            }
        return deployments_settings

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        app = self.get_object()

        context["feature_enabled"] = settings.features.app_migration.enabled
        context["app_url"] = f"https://{ app.slug }.{settings.APP_DOMAIN}"
        context["admin_options"] = User.objects.exclude(auth0_id="",).exclude(
            auth0_id__in=[user.auth0_id for user in app.admins],
        )

        context["grant_access_form"] = GrantAppAccessForm(
            app=app,
            exclude_connected=True,
        )

        context["kibana_base_url"] = settings.KIBANA_BASE_URL
        context["deployments_settings"] = AppAuthSettingsSerializer(
            self._get_all_app_settings(app)
        ).data
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

    def form_valid(self, form):
        try:
            self.object = AppManager().register_app(
                self.request.user, form.cleaned_data
            )
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

    def get_form_kwargs(self):
        kwargs = FormMixin.get_form_kwargs(self)
        env_name = self.request.GET.get("env_name")
        app = self.get_object()
        kwargs.update(
            request=self.request,
            all_connections_names=auth0.ExtendedAuth0().connections.get_all_connection_names(),  # noqa: E501
            custom_connections=auth0.ExtendedConnections.custom_connections(),
            auth0_connections=app.auth0_connections(env_name=env_name),
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
                self.object.auth0_client_name(
                    env_name=form.cleaned_data.get("env_name")
                ),
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
        context["env_name"] = self.request.GET.get("env_name")
        context["app_ip_allowlists"] = [
            {
                "text": ip_allowlist.name,
                "value": ip_allowlist.pk,
                "checked": ip_allowlist.pk
                in context["app"].env_allow_ip_ranges_ids(context["env_name"]),
            }
            for ip_allowlist in IPAllowlist.objects.filter(deleted=False)
        ]
        return context

    def form_valid(self, form):
        """
        Update the App's list of IPAllowlists, which will trigger the App's entry in
        AWS Secrets Manager to be updated (see signal app_ip_allowlists_changed() in
        App model).
        """
        app = self.get_object()
        AppIPAllowList.objects.update_ip_allowlist(
            app=self.get_object(),
            github_api_token=self.request.user.github_api_token,
            env_name=form.data.get("env_name"),
            ip_allowlists=form.cleaned_data["ip_allowlists"],
        )
        return HttpResponseRedirect(self.get_success_url(app))

    def get_success_url(self, app):
        messages.success(
            self.request,
            f"Successfully updated the IP allowlists associated with app {app.name}",  # noqa:E501
        )
        return reverse_lazy("manage-app", kwargs={"pk": app.id})


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
    allowed_methods = ["POST"]

    def form_valid(self, form):
        app = self.get_object()
        app.delete(github_api_token=self.request.user.github_api_token)
        messages.success(self.request, f"Successfully deleted {app.name} app")
        return HttpResponseRedirect(self.get_success_url())


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
    permission_required = "api.update_app_settings"
    model = App

    def get_redirect_url(self, *args, **kwargs):
        return reverse_lazy("manage-app", kwargs={"pk": kwargs["pk"]})

    def post(self, request, *args, **kwargs):
        app = self.get_object()
        env_name = dict(self.request.POST).get("env_name")[0]
        cluster.App(app).create_auth_settings(
            env_name=env_name,
            github_api_token=self.request.user.github_api_token,
        )
        return super().post(request, *args, **kwargs)


class RemoveAppAuth0(
    OIDCLoginRequiredMixin, PermissionRequiredMixin, SingleObjectMixin, RedirectView
):
    permission_required = "api.update_app_settings"
    allowed_methods = ["POST"]
    model = App

    def get_redirect_url(self, *args, **kwargs):
        return reverse_lazy("manage-app", kwargs={"pk": kwargs["pk"]})

    def post(self, request, *args, **kwargs):
        env_name = dict(self.request.POST).get("env_name")[0]
        cluster.App(self.get_object()).remove_auth_settings(
            env_name=env_name,
            github_api_token=self.request.user.github_api_token,
        )
        return super().post(request, *args, **kwargs)


class AddCustomers(OIDCLoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = App
    form_class = AddAppCustomersForm
    permission_required = "api.add_app_customer"

    def form_invalid(self, form):
        self.request.session["add_customer_form_errors"] = form.errors
        return HttpResponseRedirect(
            reverse_lazy("manage-app", kwargs={"pk": self.kwargs["pk"]}),
        )

    def form_valid(self, form):
        self.get_object().add_customers(
            form.cleaned_data["customer_email"],
            env_name=form.cleaned_data.get("env_name"),
            group_id=form.cleaned_data.get("group_id"),
        )
        return HttpResponseRedirect(
            self.get_success_url(env_name=form.cleaned_data.get("env_name"))
        )

    def get_form_kwargs(self):
        kwargs = FormMixin.get_form_kwargs(self)
        return kwargs

    def get_success_url(self, *args, **kwargs):
        messages.success(self.request, "Successfully added customers")
        return "{}?env_name={}".format(
            reverse_lazy(
                "appcustomers-page", kwargs={"pk": self.kwargs["pk"], "page_no": 1}
            ),
            kwargs.get("env_name", ""),
        )


class AppCustomersPageView(OIDCLoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = App
    permission_required = "api.retrieve_app"
    template_name = "customers-list.html"

    def _retrieve_and_confirm_env_info(self, app, context):
        env_name = self.request.GET.get("env_name") or ""
        context["deployment_envs"] = app.deployment_envs(
            self.request.user.github_api_token
        )
        if not env_name and len(context["deployment_envs"]) >= 1:
            env_name = context["deployment_envs"][0]
        context["env_name"] = env_name

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        app: App = context.get("app")

        self._retrieve_and_confirm_env_info(app, context)
        group_id = self.request.GET.get("group_id") or app.get_group_id(
            context["env_name"]
        )
        context["group_id"] = group_id
        context["page_no"] = page_no = self.kwargs.get("page_no")

        if group_id:
            customers = app.customer_paginated(page_no, group_id)
            context["customers"] = customers.get("users", [])
        else:
            customers = {}
            context["customers"] = []
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
        return reverse_lazy(
            "appcustomers-page", kwargs={"pk": self.kwargs["pk"], "page_no": 1}
        )

    def _get_env_group_info(self):
        env_names = self.request.POST.getlist("env_name")
        env_name = env_names[0] if env_names else ""
        group_ids = self.request.POST.getlist("group_id")
        group_id = group_ids[0] if group_ids else ""
        return env_name, group_id

    def perform_update(self, **kwargs):
        app = self.get_object()
        user_ids = self.request.POST.getlist("customer")
        env_name, group_id = self._get_env_group_info()
        try:
            app.delete_customers(user_ids, env_name=env_name, group_id=group_id)
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
