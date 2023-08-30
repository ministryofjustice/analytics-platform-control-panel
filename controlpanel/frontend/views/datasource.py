# Standard library
from itertools import chain

# Third-party
from django.conf import settings
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.views.generic.base import ContextMixin
from django.views.generic.detail import DetailView
from django.views.generic.edit import CreateView, DeleteView, FormMixin, UpdateView
from django.views.generic.list import ListView
from rules.contrib.views import PermissionRequiredMixin

# First-party/Local
from controlpanel.api import cluster, tasks
from controlpanel.api.elasticsearch import bucket_hits_aggregation
from controlpanel.api.models import (
    IAMManagedPolicy,
    PolicyS3Bucket,
    S3Bucket,
    User,
    UserS3Bucket,
)
from controlpanel.api.serializers import ESBucketHitsSerializer
from controlpanel.frontend.forms import (
    CreateDatasourceFolderForm,
    CreateDatasourceForm,
    GrantAccessForm,
)
from controlpanel.oidc import OIDCLoginRequiredMixin

DATASOURCE_TYPES = [
    "warehouse",
    "webapp",
]


class DatasourceMixin(ContextMixin):
    all_datasources = True
    datasource_type = None

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context["all-datasources"] = self.all_datasources
        context["datasource_type"] = self.get_datasource_type()
        return context

    def get_datasource_type(self):
        if self.datasource_type is None:
            if hasattr(self, "object") and self.object:
                if self.object.is_data_warehouse:
                    return "warehouse"
                return "webapp"
            return None
        return self.datasource_type


class BucketList(
    OIDCLoginRequiredMixin,
    PermissionRequiredMixin,
    DatasourceMixin,
    ListView,
):
    all_datasources = False
    context_object_name = "buckets"
    datasource_type = "warehouse"
    model = S3Bucket
    permission_required = "api.list_s3bucket"
    template_name = "datasource-list.html"

    def get_queryset(self):
        return S3Bucket.objects.prefetch_related("users3buckets").filter(
            is_data_warehouse=self.datasource_type == "warehouse",
            users3buckets__user=self.request.user,
        )

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)

        all_datasources = S3Bucket.objects.prefetch_related(
            "users3buckets__user"
        ).filter(
            is_data_warehouse=self.datasource_type == "warehouse",
        )
        other_datasources = all_datasources.exclude(id__in=self.get_queryset())
        other_datasources_admins = {}
        for datasource in other_datasources:
            admins = [
                m2m.user for m2m in datasource.users3buckets.filter(is_admin=True)
            ]
            other_datasources_admins[datasource.id] = admins

        context["other_datasources"] = other_datasources
        context["other_datasources_admins"] = other_datasources_admins
        return context


class AdminBucketList(BucketList):
    all_datasources = True
    permission_required = "api.is_superuser"

    def get_queryset(self):
        return S3Bucket.objects.prefetch_related("users3buckets").all()


class WebappBucketList(BucketList):
    datasource_type = "webapp"


class BucketDetail(
    OIDCLoginRequiredMixin,
    PermissionRequiredMixin,
    DatasourceMixin,
    DetailView,
):
    context_object_name = "bucket"
    model = S3Bucket
    permission_required = "api.retrieve_s3bucket"
    template_name = "datasource-detail.html"

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        bucket = kwargs["object"]
        access_users = bucket.users3buckets.all().select_related("user")
        member_ids = [member.user.auth0_id for member in access_users]
        context["access_logs"] = ESBucketHitsSerializer(
            bucket_hits_aggregation(bucket.name)
        ).data
        context["users_options"] = User.objects.exclude(auth0_id__isnull=True).exclude(
            auth0_id__in=member_ids
        )
        access_policies = bucket.policys3buckets.all().select_related("policy")
        policy_ids = [access.policy.id for access in access_policies]
        context["policies_options"] = IAMManagedPolicy.objects.exclude(
            pk__in=policy_ids
        )
        context["access_list"] = list(chain(access_users, access_policies))
        return context


class CreateDatasource(
    OIDCLoginRequiredMixin,
    PermissionRequiredMixin,
    DatasourceMixin,
    CreateView,
):
    model = S3Bucket
    permission_required = "api.create_s3bucket"
    template_name = "datasource-create.html"

    def get_context_data(self, **kwargs):
        if "type" in self.request.GET and self.request.GET["type"] in DATASOURCE_TYPES:
            self.datasource_type = self.request.GET["type"]
        return super().get_context_data(**kwargs)

    def get_form_kwargs(self):
        return FormMixin.get_form_kwargs(self)

    def get_success_url(self):
        return reverse_lazy("manage-datasource", kwargs={"pk": self.object.pk})

    def get_form_class(self):
        if self.request.GET.get("type") == "webapp":
            return CreateDatasourceForm
        if settings.features.s3_folders.enabled:
            return CreateDatasourceFolderForm
        return CreateDatasourceForm

    def form_valid(self, form):
        name = form.cleaned_data["name"]
        datasource_type = self.request.GET.get("type")

        try:
            with transaction.atomic():
                self.object = S3Bucket.objects.create(
                    name=name,
                    created_by=self.request.user,
                    is_data_warehouse=datasource_type == "warehouse",
                    send_task=False
                )
                messages.success(
                    self.request,
                    f"Successfully created {name} {datasource_type} data source",
                )
                transaction.on_commit(tasks.S3BucketCreate(self.object, self.request.user).create_task)
        except Exception as ex:
            form.add_error("name", str(ex))
            return FormMixin.form_invalid(self, form)
        return FormMixin.form_valid(self, form)


class DeleteDatasource(
    OIDCLoginRequiredMixin,
    PermissionRequiredMixin,
    DeleteView,
):
    model = S3Bucket
    permission_required = "api.destroy_s3bucket"
    success_url = reverse_lazy("list-warehouse-datasources")

    def delete(self, *args, **kwargs):
        bucket = self.get_object()
        if not bucket.is_data_warehouse:
            self.success_url = reverse_lazy("list-webapp-datasources")

        response = super().delete(*args, **kwargs)

        messages.success(self.request, "Successfully deleted data source")

        return response


class UpdateAccessLevelMixin:
    context_object_name = "items3bucket"
    form_class = GrantAccessForm
    model = None
    permission_required = "api.update_users3bucket"
    template_name = "datasource-access-update.html"

    def get_initial(self):
        initial = self.initial.copy()
        if hasattr(self, "object"):
            initial.update(self.object.__dict__)
        return initial

    def get_form_kwargs(self):
        return FormMixin.get_form_kwargs(self)

    def get_success_url(self):
        messages.success(self.request, "Successfully updated access")
        return reverse_lazy("manage-datasource", kwargs={"pk": self.object.s3bucket.id})

    def form_valid(self, form):
        self.object.access_level = form.cleaned_data["access_level"]
        self.object.is_admin = form.cleaned_data.get("is_admin")
        self.object.current_user = self.request.user
        self.object.paths = form.cleaned_data["paths"]
        self.object.save()
        return FormMixin.form_valid(self, form)


class UpdateAccessLevel(
    UpdateAccessLevelMixin,
    OIDCLoginRequiredMixin,
    PermissionRequiredMixin,
    UpdateView,
):
    model = UserS3Bucket

    def get_context_data(self, **kwargs):
        context_data = super().get_context_data(**kwargs)
        context_data.update(
            {
                "revoke_url": reverse_lazy(
                    "revoke-datasource-access", kwargs={"pk": self.object.id}
                ),
                "action_url": reverse_lazy(
                    "update-access-level", kwargs={"pk": self.object.id}
                ),
                "entity_type": "user",
                "entity_id": self.object.user.id,
            }
        )
        return context_data


class UpdateIAMManagedPolicyAccessLevel(
    UpdateAccessLevelMixin,
    OIDCLoginRequiredMixin,
    PermissionRequiredMixin,
    UpdateView,
):
    model = PolicyS3Bucket

    def get_context_data(self, **kwargs):
        context_data = super().get_context_data(**kwargs)
        context_data.update(
            {
                "revoke_url": reverse_lazy(
                    "revoke-datasource-policy-access", kwargs={"pk": self.object.id}
                ),
                "action_url": reverse_lazy(
                    "update-policy-access-level", kwargs={"pk": self.object.id}
                ),
                "entity_type": "group",
                "entity_id": self.object.policy.id,
            }
        )
        return context_data


class RevokeAccess(OIDCLoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = UserS3Bucket
    permission_required = "api.destroy_users3bucket"

    def get_success_url(self):
        messages.success(self.request, "Successfully revoked access")
        return reverse_lazy("manage-datasource", kwargs={"pk": self.object.s3bucket.id})


class RevokeIAMManagedPolicyAccess(RevokeAccess):
    model = PolicyS3Bucket


class GrantAccessMixin:
    form_class = GrantAccessForm
    template_name = "datasource-access-grant.html"

    def get_form_kwargs(self):
        return FormMixin.get_form_kwargs(self)

    def get_success_url(self):
        messages.success(self.request, "Successfully granted access")
        return reverse_lazy("manage-datasource", kwargs={"pk": self.object.s3bucket.id})

    def form_valid(self, form):
        user = self.request.user
        bucket = get_object_or_404(S3Bucket, pk=self.kwargs["pk"])

        if not user.has_perm("api.grant_s3bucket_access", bucket):
            raise PermissionDenied()

        is_admin = form.cleaned_data.get("is_admin")

        if is_admin and not user.has_perm("api.add_s3bucket_admin", bucket):
            raise PermissionDenied()

        self.object = self.model.objects.create(
            current_user=self.request.user,
            **self.values(form))
        return FormMixin.form_valid(self, form)


class GrantAccess(
    GrantAccessMixin,
    OIDCLoginRequiredMixin,
    PermissionRequiredMixin,
    CreateView,
):
    context_object_name = "users3bucket"
    model = UserS3Bucket
    permission_required = "api.create_users3bucket"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        bucket = get_object_or_404(S3Bucket, pk=self.kwargs["pk"])
        context["bucket"] = bucket
        member_ids = list(
            bucket.users3buckets.all()
            .select_related("user")
            .values_list(
                "user__auth0_id",
                flat=True,
            )
        )
        context["entity_options"] = User.objects.exclude(auth0_id__isnull=True).exclude(
            auth0_id__in=member_ids,
        )
        context["entity_type"] = "user"
        context["grant_url"] = reverse_lazy(
            "grant-datasource-access", kwargs={"pk": bucket.id}
        )
        return context

    def values(self, form):
        return {
            "access_level": form.cleaned_data["access_level"],
            "s3bucket_id": self.kwargs["pk"],
            "paths": form.cleaned_data["paths"],
            "is_admin": form.cleaned_data.get("is_admin"),
            "user_id": form.cleaned_data["user_id"],
        }


class GrantPolicyAccess(
    GrantAccessMixin,
    OIDCLoginRequiredMixin,
    PermissionRequiredMixin,
    CreateView,
):
    context_object_name = "policys3bucket"
    model = PolicyS3Bucket
    permission_required = "api.create_policys3bucket"

    def get_context_data(self):
        context = super().get_context_data()
        bucket = get_object_or_404(S3Bucket, pk=self.kwargs["pk"])
        context["bucket"] = bucket
        access_policies = bucket.policys3buckets.all().select_related("policy")
        policy_ids = [access.policy.id for access in access_policies]
        context["access_policies"] = access_policies
        context["entity_options"] = IAMManagedPolicy.objects.exclude(pk__in=policy_ids)
        context["entity_type"] = "group"
        context["grant_url"] = reverse_lazy(
            "grant-datasource-policy-access", kwargs={"pk": bucket.id}
        )
        return context

    def values(self, form):
        return {
            "access_level": form.cleaned_data["access_level"],
            "s3bucket_id": self.kwargs["pk"],
            "paths": form.cleaned_data["paths"],
            "policy_id": form.cleaned_data["policy_id"],
        }
