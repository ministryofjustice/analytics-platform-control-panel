# Standard library
from typing import List

# Third-party
import botocore
import requests
import sentry_sdk
import structlog
from auth0.rest import Auth0Error
from django.conf import settings
from django.contrib import messages
from django.contrib.postgres.aggregates import StringAgg
from django.db import transaction
from django.db.models import F, Prefetch
from django.db.models.functions import Coalesce
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.template.defaultfilters import pluralize
from django.urls import reverse_lazy
from django.utils.http import urlencode
from django.views.generic.base import RedirectView, View
from django.views.generic.detail import DetailView, SingleObjectMixin
from django.views.generic.edit import CreateView, DeleteView, FormMixin, UpdateView
from django.views.generic.list import ListView
from rules.contrib.views import PermissionRequiredMixin

# First-party/Local
from controlpanel.api import auth0, cluster
from controlpanel.api.github import GithubAPI, RepositoryNotFound
from controlpanel.api.models import (
    App,
    AppIPAllowList,
    AppS3Bucket,
    IPAllowlist,
    Task,
    User,
    UserApp,
)
from controlpanel.api.pagination import Auth0Paginator
from controlpanel.api.serializers import AppAuthSettingsSerializer
from controlpanel.frontend.forms import (
    AddAppCustomersForm,
    CloudPlatformArnForm,
    CreateAppForm,
    GrantAppAccessForm,
    RemoveCustomerByEmailForm,
    UpdateAppAuth0ConnectionsForm,
)
from controlpanel.frontend.mixins import CsvWriterMixin, PolicyAccessMixin
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
    template_name = "webapp-admin-list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["all_webapps"] = True
        return context

    def get_queryset(self):
        userapps = UserApp.objects.filter(is_admin=True).exclude(user_id="").select_related("user")
        return App.objects.all().prefetch_related(
            Prefetch("userapps", queryset=userapps, to_attr="app_admins")
        )


class AppAdminCSV(CsvWriterMixin, View):
    filename = "app_admins"
    csv_headings = ["App Name", "Admins", "Emails"]
    model_attributes = ["name", "users", "emails"]

    def post(self, request, *args, **kwargs):
        apps = (
            App.objects.filter(userapps__is_admin=True)
            .annotate(
                users=StringAgg("userapps__user__username", delimiter=", "),
                emails=StringAgg(
                    Coalesce("userapps__user__justice_email", "userapps__user__email"),
                    delimiter=", ",
                ),
            )
            .values("name", "users", "emails")
            .order_by("name")
        )

        return self.write_csv(apps)


class AppDetail(OIDCLoginRequiredMixin, PermissionRequiredMixin, DetailView):
    context_object_name = "app"
    model = App
    permission_required = "api.retrieve_app"
    template_name = "webapp-detail.html"

    def _get_all_app_settings(self, app):
        app_manager_ins = cluster.App(app, self.request.user.github_api_token)
        access_repo_error_msg = None
        github_settings_access_error_msg = None
        try:
            # NB: if this call fails....
            deployment_env_names = app_manager_ins.get_deployment_envs()
        except requests.exceptions.HTTPError as ex:
            access_repo_error_msg = ex.__str__()
            github_settings_access_error_msg = ex.__str__()
            # ...this is set to empty list...
            deployment_env_names = []
        # ...which means this will remain empty dict...
        deployments_settings = {}
        auth0_connections = app.auth0_connections_by_env()
        # ...so no call to get secrets/variables is made
        try:
            for env_name in deployment_env_names:
                deployments_settings[env_name] = {
                    "secrets": app_manager_ins.get_env_secrets(env_name=env_name),
                    "variables": app_manager_ins.get_env_vars(env_name=env_name),
                    "connections": auth0_connections.get(env_name, {}).get("connections") or [],
                }
        except requests.exceptions.HTTPError as ex:
            github_settings_access_error_msg = ex.__str__()
        # ...knock on effect is in serializers.py these envs will be marked as redundant
        return deployments_settings, access_repo_error_msg, github_settings_access_error_msg

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        app = self.get_object()

        context["admin_options"] = User.objects.exclude(
            auth0_id="",
        ).exclude(
            auth0_id__in=[user.auth0_id for user in app.admins],
        )

        context["grant_access_form"] = GrantAppAccessForm(
            app=app,
            user=self.request.user,
        )

        errors = self.request.session.pop("cloud_form_errors", None)
        cloud_form = CloudPlatformArnForm()
        cloud_form._errors = errors
        context["cloud_platform_access_form"] = cloud_form

        # If auth settings not returned, all envs marked redundant in the serializer.
        # Should hide them instead?
        auth_settings, access_repo_error_msg, github_settings_access_error_msg = (
            self._get_all_app_settings(app)
        )
        auth0_clients_status = app.auth0_clients_status()
        context["deployments_settings"] = AppAuthSettingsSerializer(
            dict(auth_settings=auth_settings, auth0_clients_status=auth0_clients_status)
        ).data
        context["repo_access_error_msg"] = access_repo_error_msg
        context["github_settings_access_error_msg"] = github_settings_access_error_msg

        context["app_log_urls"] = {}
        for env_name in context["deployments_settings"].keys():
            context["app_log_urls"].update({env_name: app.get_logs_url(env=env_name)})

        context["show_cloud_platform_assume_role"] = (
            settings.features.cloud_platform_assume_role.enabled
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
        )
        return kwargs

    def get_success_url(self):
        messages.success(
            self.request,
            f"Successfully registered {self.object.name} webapp",
        )
        return reverse_lazy("manage-app", kwargs={"pk": self.object.pk})

    def _check_namespace_in_cloud_platform(self, form_namespace):
        """Throws RepositoryNotFound error if namespace not found in CP repo"""

        namespace = f"{form_namespace}-{settings.ENV}"
        cloud_platform_repo_name = "cloud-platform-environments"
        path = f"namespaces/live.cloud-platform.service.justice.gov.uk/{namespace}"
        GithubAPI(self.request.user.github_api_token).get_repository_contents(
            cloud_platform_repo_name, path
        )

    def form_valid(self, form):
        try:
            self._check_namespace_in_cloud_platform(form.cleaned_data.get("namespace"))

            self.object = AppManager().register_app(self.request.user, form.cleaned_data)
        except RepositoryNotFound:
            form.add_error("namespace", "Namespace doesn't exist in cloud platform")
            return FormMixin.form_invalid(self, form)
        except Exception as ex:
            form.add_error("repo_url", str(ex))
            return FormMixin.form_invalid(self, form)
        return FormMixin.form_valid(self, form)

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context["show_cloud_platform_assume_role"] = (
            settings.features.cloud_platform_assume_role.enabled
        )
        return context


class UpdateAppAuth0Connections(OIDCLoginRequiredMixin, PermissionRequiredMixin, UpdateView):

    form_class = UpdateAppAuth0ConnectionsForm
    model = App
    permission_required = "api.create_connections"
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
            cluster.App(
                app=self.get_object(), github_api_token=self.request.user.github_api_token
            ).update_auth_connections(
                env_name=form.cleaned_data.get("env_name"),
                new_conns=form.cleaned_data.get("auth0_connections"),
            )
        except Exception as ex:
            form.add_error("connections", str(ex))
            return FormMixin.form_invalid(self, form)
        return FormMixin.form_valid(self, form)


class UpdateAppIPAllowlists(OIDCLoginRequiredMixin, PermissionRequiredMixin, UpdateView):

    model = App
    template_name = "webapp-update-ip-allowlists.html"
    permission_required = "api.update_app_ip_allowlists"
    fields = ["ip_allowlists"]

    def format_ip_allowlists(self, allowlist):
        # splits larger ip allowlists into multiple lines

        allowlist = allowlist.replace(",", ", ")
        return allowlist

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context["app"] = self.get_object()
        context["env_name"] = self.request.GET.get("env_name")

        context["app_ip_allowlists"] = [
            {
                "text": ip_allowlist.name,
                "value": ip_allowlist.pk,
                "hint": {
                    "text": self.format_ip_allowlists(ip_allowlist.allowed_ip_ranges),
                },
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
    UpdateView,
):
    form_class = GrantAppAccessForm
    model = App
    permission_required = "api.add_app_bucket"

    def get_form_kwargs(self):
        kwargs = FormMixin.get_form_kwargs(self)
        if "app" not in kwargs:
            kwargs["app"] = App.objects.get(pk=self.kwargs["pk"])
        kwargs["user"] = self.request.user
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
            self.object.current_user = self.request.user
            self.object.save()
        except AppS3Bucket.DoesNotExist:
            self.object = AppS3Bucket.objects.create(
                access_level=form.cleaned_data["access_level"],
                app_id=self.kwargs["pk"],
                s3bucket=form.cleaned_data["datasource"],
                current_user=self.request.user,
            )
        return FormMixin.form_valid(self, form)

    def form_invalid(self, form):
        # It should be impossible to get here. The form consists of
        # ChoiceFields, so the only way an invalid input can be submitted is by
        # constructing the request manually - in which (suspicious) case we should
        # return as little information as possible
        log.warning("Received suspicious invalid grant app access request")
        raise Exception(form.errors)


class EnableBedrockApp(PolicyAccessMixin, UpdateView):
    model = App
    fields = ["is_bedrock_enabled"]
    success_message = "Successfully updated bedrock status"
    method_name = "set_bedrock_access"


class EnableTextractApp(PolicyAccessMixin, UpdateView):
    model = App
    fields = ["is_textract_enabled"]
    success_message = "Successfully updated textract status"
    method_name = "set_textract_access"


class UpdateCloudPlatformRoleArn(
    OIDCLoginRequiredMixin,
    PermissionRequiredMixin,
    UpdateView,
):
    form_class = CloudPlatformArnForm
    model = App
    permission_required = "api.add_cloud_platform_arn"

    def get_form_kwargs(self):
        kwargs = FormMixin.get_form_kwargs(self)
        return kwargs

    def get_success_url(self):
        return reverse_lazy("manage-app", kwargs={"pk": self.object.id})

    def form_valid(self, form):
        try:
            with transaction.atomic():
                app = self.get_object()
                app.cloud_platform_role_arn = form.cleaned_data.get("cloud_platform_role_arn")
                app.save()
                app.update_cloud_platform_access()
                messages.success(self.request, "Successfully updated cloud platform ARN")
                return HttpResponseRedirect(self.get_success_url())

        except botocore.exceptions.ClientError as e:
            log.warning(f"failed to add cloud platform ARN - {e}")
            messages.error(
                self.request,
                "Failed to add cloud platform ARN. If this persists, please raise a support ticket",
            )
            return HttpResponseRedirect(self.get_success_url())

    def form_invalid(self, form):
        messages.error(self.request, "Failed to update Cloud Platform role ARN")
        self.request.session["cloud_form_errors"] = form.errors
        return HttpResponseRedirect(self.get_success_url())


class RevokeAppAccess(OIDCLoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = AppS3Bucket
    permission_required = "api.remove_app_bucket"

    def get_object(self, queryset=None):
        obj = super().get_object(queryset=queryset)
        obj.current_user = self.request.user
        return obj

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
            return reverse_lazy("manage-datasource", kwargs={"pk": self.object.s3bucket.id})
        return reverse_lazy("manage-app", kwargs={"pk": self.object.app.id})

    def form_valid(self, form):
        self.object = self.get_object()
        self.object.access_level = form.cleaned_data.get("access_level")
        self.object.current_user = self.request.user
        self.object.save()
        return HttpResponseRedirect(self.get_success_url())


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
        cluster.App(app, self.request.user.github_api_token).create_auth_settings(env_name=env_name)
        return super().post(request, *args, **kwargs)


class M2MClientMixin(
    OIDCLoginRequiredMixin,
    PermissionRequiredMixin,
    SingleObjectMixin,
):
    http_method_names = ["post"]
    permission_required = "api.update_app_settings"
    model = App

    def get_redirect_url(self, *args, **kwargs):
        return reverse_lazy("manage-app", kwargs={"pk": kwargs["pk"]})


class SetupM2MClient(M2MClientMixin, RedirectView):

    def post(self, request, *args, **kwargs):
        app = self.get_object()
        client = cluster.App(app, self.request.user.github_api_token).create_m2m_client()
        messages.success(
            self.request,
            f"Successfully created machine-to-machine client. Your client credentials are shown below, ensure to store them securely as you will not be able to view them again.",  # noqa
        )
        messages.info(self.request, f"Client ID: {client['client_id']}")
        messages.info(self.request, f"Client Secret: {client['client_secret']}")
        return super().post(request, *args, **kwargs)


class RotateM2MCredentials(M2MClientMixin, RedirectView):

    def post(self, request, *args, **kwargs):
        app = self.get_object()
        client = cluster.App(app, self.request.user.github_api_token).rotate_m2m_client_secret()
        if not client:
            messages.error(
                self.request,
                "Failed to find a machine-to-machine client for this app, please try creating a new one.",  # noqa
            )
            return self.get(request, *args, **kwargs)

        messages.success(
            self.request,
            f"Successfully rotated machine-to-machine client secret. Your client ID and new client secret are shown below, ensure to store them securely as you will not be able to view them again.",  # noqa
        )
        messages.info(self.request, f"Client ID: {client['client_id']}")
        messages.info(self.request, f"Client Secret: {client['client_secret']}")
        return super().post(request, *args, **kwargs)


class DeleteM2MClient(M2MClientMixin, RedirectView):

    def post(self, request, *args, **kwargs):
        app = self.get_object()
        cluster.App(app, self.request.user.github_api_token).delete_m2m_client()
        messages.success(self.request, "Successfully deleted machine-to-machine client.")
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
        cluster.App(
            self.get_object(), github_api_token=self.request.user.github_api_token
        ).remove_auth_settings(env_name=env_name)
        return super().post(request, *args, **kwargs)


class RemoveAppDeploymentEnv(
    OIDCLoginRequiredMixin, PermissionRequiredMixin, SingleObjectMixin, RedirectView
):
    permission_required = "api.update_app_settings"
    allowed_methods = ["POST"]
    model = App

    def get_redirect_url(self, *args, **kwargs):
        return reverse_lazy("manage-app", kwargs={"pk": kwargs["pk"]})

    def post(self, request, *args, **kwargs):
        env_name = kwargs.get("env_name")
        cluster.App(self.get_object()).remove_redundant_env(env_name=env_name)
        return super().post(request, *args, **kwargs)


class AddCustomers(OIDCLoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = App
    form_class = AddAppCustomersForm
    permission_required = "api.add_app_customer"

    def form_invalid(self, form):
        self.request.session["add_customer_form_errors"] = form.errors
        return HttpResponseRedirect(self.get_success_url())

    def form_valid(self, form):
        self.get_object().add_customers(
            form.cleaned_data["customer_email"],
            group_id=self.kwargs.get("group_id"),
        )
        messages.success(self.request, "Successfully added customers")
        return HttpResponseRedirect(self.get_success_url())

    def get_form_kwargs(self):
        kwargs = FormMixin.get_form_kwargs(self)
        return kwargs

    def get_success_url(self, *args, **kwargs):
        url = reverse_lazy("appcustomers-page", kwargs={"pk": self.kwargs["pk"], "page_no": 1})
        return url + "?" + urlencode({"group_id": self.kwargs.get("group_id")})


class AppCustomersPageView(OIDCLoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = App
    permission_required = "api.retrieve_app"
    template_name = "customers-list.html"

    def _confirm_group_id(self, context):
        group_id = self.request.GET.get("group_id")
        if not group_id and context.get("groups_dict"):
            group_id = list(context["groups_dict"].keys())[0]
        return group_id

    def _get_customer_list(self, context, page_no, app):
        read_customer_error_msg = None
        group_id = context["group_id"]
        if group_id:
            try:
                customers = app.customer_paginated(page_no, group_id)
            except Auth0Error as error:
                customers = {}
                read_customer_error_msg = error.__str__()
        else:
            customers = {}
        return customers, read_customer_error_msg

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        app: App = context.get("app")

        context["groups_dict"] = app.get_auth0_group_list()
        context["group_id"] = self._confirm_group_id(context)
        context["page_no"] = page_no = self.kwargs.get("page_no")
        customers, read_customer_error_msg = self._get_customer_list(context, page_no, app)
        context["auth_errors"] = {context["group_id"]: read_customer_error_msg}
        context["customers"] = customers.get("users", [])
        context["paginator"] = paginator = self._paginate_customers(customers)
        context["elided"] = paginator.get_elided_page_range(page_no)
        context["remove_customer_form"] = RemoveCustomerByEmailForm(
            initial={
                "group_id": context["group_id"],
            }
        )
        return context

    def _paginate_customers(self, auth_results: List[dict], per_page=25):
        total_count = auth_results.get("total", 0)
        customer_result = auth_results.get("users", [])
        paginator = Auth0Paginator(customer_result, per_page=per_page, total_count=total_count)
        return paginator


class RemoveCustomer(UpdateApp):
    permission_required = "api.remove_app_customer"

    def get_redirect_url(self, *args, **kwargs):
        return "{}?group_id={}".format(
            reverse_lazy("appcustomers-page", kwargs={"pk": self.kwargs["pk"], "page_no": 1}),
            kwargs.get("group_id"),
        )

    def perform_update(self, **kwargs):
        app = self.get_object()
        user_ids = self.request.POST.getlist("customer")
        try:
            app.delete_customers(user_ids, group_id=kwargs.get("group_id"))
        except App.DeleteCustomerError as e:
            sentry_sdk.capture_exception(e)
            messages.error(self.request, f"Failed removing customer{pluralize(user_ids)}")
        else:
            messages.success(self.request, f"Successfully removed customer{pluralize(user_ids)}")


class RemoveCustomerByEmail(UpdateApp):
    permission_required = "api.remove_app_customer"
    form = None

    def get_redirect_url(self, *args, **kwargs):
        return "{}?group_id={}".format(
            reverse_lazy("appcustomers-page", kwargs={"pk": self.kwargs["pk"], "page_no": 1}),
            kwargs.get("group_id"),
        )

    def perform_update(self, **kwargs):
        """
        Attempts to remove a user from a group, based on their email address
        """
        self.form = RemoveCustomerByEmailForm(data=self.request.POST)
        if not self.form.is_valid():
            return messages.error(self.request, "Invalid email address entered")

        app = self.get_object()
        email = self.form.cleaned_data["email"]
        try:
            app.delete_customer_by_email(email=email, group_id=str(kwargs.get("group_id")))
        except App.DeleteCustomerError as e:
            return messages.error(
                self.request, str(e) or f"Couldn't remove customer with email {email}"
            )

        messages.success(self.request, f"Successfully removed customer {email}")


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
