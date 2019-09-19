from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.views.generic.base import ContextMixin
from django.views.generic.detail import DetailView
from django.views.generic.edit import (
    CreateView,
    DeleteView,
    FormMixin,
    UpdateView,
)
from django.views.generic.list import ListView
from rules.contrib.views import PermissionRequiredMixin

from controlpanel.api.elasticsearch import bucket_hits_aggregation
from controlpanel.api.models import (
    IAMManagedPolicy,
    S3Bucket,
    User,
    UserS3Bucket,
    PolicyS3Bucket)
from controlpanel.api.serializers import ESBucketHitsSerializer
from controlpanel.frontend.forms import (
    CreateDatasourceForm,
    GrantAccessForm,
    GrantIAMManagedPolicyAccessForm)


DATASOURCE_TYPES = [
    'warehouse',
    'webapp',
]


class DatasourceMixin(ContextMixin):
    all_datasources = True
    datasource_type = None

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context['all-datasources'] = self.all_datasources
        context['datasource_type'] = self.get_datasource_type()
        return context

    def get_datasource_type(self):
        if self.datasource_type is None:
            if hasattr(self, 'object') and self.object:
                if self.object.is_data_warehouse:
                    return "warehouse"
                return "webapp"
            return None
        return self.datasource_type


class BucketList(
    LoginRequiredMixin,
    PermissionRequiredMixin,
    DatasourceMixin,
    ListView,
):
    all_datasources = False
    context_object_name = 'buckets'
    datasource_type = 'warehouse'
    model = S3Bucket
    permission_required = 'api.list_s3bucket'
    template_name = "datasource-list.html"

    def get_queryset(self):
        return S3Bucket.objects.prefetch_related('users3buckets').filter(
            is_data_warehouse=self.datasource_type == 'warehouse',
            users3buckets__user=self.request.user,
        )


class AdminBucketList(BucketList):
    all_datasources = True
    permission_required = 'api.is_superuser'

    def get_queryset(self):
        return S3Bucket.objects.prefetch_related('users3buckets').all()


class WebappBucketList(BucketList):
    datasource_type = "webapp"


class BucketDetail(
    LoginRequiredMixin,
    PermissionRequiredMixin,
    DatasourceMixin,
    DetailView,
):
    context_object_name = 'bucket'
    model = S3Bucket
    permission_required = 'api.retrieve_s3bucket'
    template_name = "datasource-detail.html"

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        bucket = kwargs['object']
        access_users = bucket.users3buckets.all().select_related('user')
        member_ids = [member.user.auth0_id for member in access_users]
        context['access_users'] = access_users
        context['access_logs'] = ESBucketHitsSerializer(
            bucket_hits_aggregation(bucket.name)
        ).data
        context['grant_access_form'] = GrantAccessForm()
        context['users_options'] = User.objects.exclude(
            auth0_id__isnull=True
        ).exclude(
            auth0_id__in=member_ids
        )
        access_policies = bucket.policys3buckets.all().select_related('policy')
        policy_ids = [access.policy.id for access in access_policies]
        context['access_policies'] = access_policies
        context['policies_options'] = IAMManagedPolicy.objects.exclude(
            pk__in=policy_ids
        )
        return context


class CreateDatasource(
    LoginRequiredMixin,
    PermissionRequiredMixin,
    DatasourceMixin,
    CreateView,
):
    form_class = CreateDatasourceForm
    model = S3Bucket
    permission_required = 'api.create_s3bucket'
    template_name = "datasource-create.html"

    def get_context_data(self, **kwargs):
        if 'type' in self.request.GET and self.request.GET['type'] in DATASOURCE_TYPES:
            self.datasource_type = self.request.GET['type']
        return super().get_context_data(**kwargs)

    def get_form_kwargs(self):
        return FormMixin.get_form_kwargs(self)

    def get_success_url(self):
        return reverse_lazy("manage-datasource", kwargs={"pk": self.object.pk})

    def form_valid(self, form):
        name = form.cleaned_data['name']
        datasource_type = self.request.GET.get("type")
        self.object = S3Bucket.objects.create(
            name=name,
            created_by=self.request.user,
            is_data_warehouse=datasource_type == "warehouse",
        )
        messages.success(
            self.request,
            f"Successfully created {name} {datasource_type} data source",
        )
        return FormMixin.form_valid(self, form)


class DeleteDatasource(
    LoginRequiredMixin,
    PermissionRequiredMixin,
    DeleteView,
):
    model = S3Bucket
    permission_required = 'api.destroy_s3bucket'
    success_url = reverse_lazy('list-warehouse-datasources')

    def delete(self, *args, **kwargs):
        bucket = self.get_object()
        session = self.request.session
        user = self.request.user

        if not bucket.is_data_warehouse:
            self.success_url = reverse_lazy('list-webapp-datasources')

        response = super().delete(*args, **kwargs)

        messages.success(self.request, "Successfully deleted data source")

        return response


class UpdateAccessLevelMixin:
    context_object_name = 'items3bucket'
    form_class = None
    model = None
    permission_required = 'api.update_users3bucket'
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
        self.object.access_level = form.cleaned_data['access_level']
        self.object.is_admin = form.cleaned_data.get('is_admin')
        self.object.paths = form.cleaned_data['paths']
        self.object.save()
        return FormMixin.form_valid(self, form)


class UpdateAccessLevel(
    UpdateAccessLevelMixin,
    LoginRequiredMixin,
    PermissionRequiredMixin,
    UpdateView,
):
    form_class = GrantAccessForm
    model = UserS3Bucket


class UpdateIAMManagedPolicyAccessLevel(
    UpdateAccessLevelMixin,
    LoginRequiredMixin,
    PermissionRequiredMixin,
    UpdateView,
):
    form_class = GrantIAMManagedPolicyAccessForm
    model = PolicyS3Bucket


class RevokeAccess(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = UserS3Bucket
    permission_required = 'api.destroy_users3bucket'

    def get_success_url(self):
        messages.success(self.request, "Successfully revoked access")
        return reverse_lazy("manage-datasource", kwargs={"pk": self.object.s3bucket.id})


class RevokeIAMManagedPolicyAccess(RevokeAccess):
    model = PolicyS3Bucket


class GrantAccess(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    context_object_name = 'users3bucket'
    form_class = GrantAccessForm
    model = UserS3Bucket
    permission_required = 'api.create_users3bucket'
    template_name = 'datasource-access-grant.html'

    def get_form_kwargs(self):
        return FormMixin.get_form_kwargs(self)

    def get_context_data(self):
        context = super().get_context_data()
        bucket = get_object_or_404(S3Bucket, pk=self.kwargs['pk'])
        context['bucket'] = bucket
        member_ids = list(bucket.users3buckets.all().select_related('user').values_list(
            'user__auth0_id',
            flat=True,
        ))
        context['users_options'] = User.objects.exclude(
            auth0_id__isnull=True
        ).exclude(
            auth0_id__in=member_ids,
        )
        context['grant_access_form'] = GrantAccessForm()
        access_policies = bucket.policys3buckets.all().select_related('policy')
        policy_ids = [access.policy.id for access in access_policies]
        context['access_policies'] = access_policies
        context['policies_options'] = IAMManagedPolicy.objects.exclude(
            pk__in=policy_ids
        )
        return context

    def get_form_class(self):
        if self.request.POST.get('policy_id'):
            return GrantIAMManagedPolicyAccessForm
        return self.form_class

    def form_invalid(self, form):
        bucket = get_object_or_404(S3Bucket, pk=self.kwargs['pk'])
        return HttpResponseRedirect(
            reverse_lazy(
                "manage-datasource",
                kwargs={"pk": bucket.id}
            )
        )

    def get_success_url(self):
        messages.success(self.request, "Successfully granted access")
        return reverse_lazy(
            "manage-datasource",
            kwargs={"pk": self.object.s3bucket.id}
        )

    def form_valid(self, form):
        user = self.request.user
        bucket = get_object_or_404(S3Bucket, pk=self.kwargs['pk'])

        if not user.has_perm('api.grant_s3bucket_access', bucket):
            raise PermissionDenied()

        is_admin = form.cleaned_data.get('is_admin')

        if is_admin and not user.has_perm('api.add_s3bucket_admin', bucket):
            raise PermissionDenied()

        values = {
            "access_level": form.cleaned_data['access_level'],
            "s3bucket_id": self.kwargs['pk'],
            "paths": form.cleaned_data['paths']
        }

        if form.cleaned_data.get('user_id'):
            model = UserS3Bucket
            values["is_admin"] = is_admin
            values["user_id"] = form.cleaned_data['user_id']
        elif form.cleaned_data.get('policy_id'):
            model = PolicyS3Bucket
            values["policy_id"] = form.cleaned_data['policy_id']

        self.object = model.objects.create(**values)
        return FormMixin.form_valid(self, form)


class GrantPolicyAccess(GrantAccess):
    context_object_name = 'users3bucket'
    form_class = GrantIAMManagedPolicyAccessForm
    model = PolicyS3Bucket
    permission_required = 'api.create_policys3bucket'
    template_name = 'datasource-policy-access-grant.html'
