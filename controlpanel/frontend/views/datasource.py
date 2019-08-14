from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
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
    S3Bucket,
    User,
    UserS3Bucket,
)
from controlpanel.api.serializers import ESBucketHitsSerializer
from controlpanel.frontend.forms import (
    CreateDatasourceForm,
    GrantAccessForm,
)


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
        access_group = bucket.users3buckets.all().select_related('user')
        member_ids = [member.user.auth0_id for member in access_group]
        context['access_group'] = access_group
        context['access_logs'] = ESBucketHitsSerializer(
            bucket_hits_aggregation(bucket.name)
        ).data
        context['grant_access_form'] = GrantAccessForm()
        context['users_options'] = User.objects.exclude(
            auth0_id__isnull=True,
            auth0_id__in=member_ids,
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
            is_data_warehouse=datasource_type == "warehouse",
        )
        UserS3Bucket.objects.create(
            s3bucket=self.object,
            user=self.request.user,
            is_admin=True,
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

    def get_success_url(self):
        messages.success(self.request, "Successfully delete data source")
        return reverse_lazy("list-all-datasources")


class UpdateAccessLevel(
    LoginRequiredMixin,
    PermissionRequiredMixin,
    UpdateView,
):
    context_object_name = 'users3bucket'
    form_class = GrantAccessForm
    model = UserS3Bucket
    permission_required = 'api.update_users3bucket'
    template_name = "datasource-access-update.html"

    def get_form_kwargs(self):
        return FormMixin.get_form_kwargs(self)

    def get_success_url(self):
        messages.success(self.request, "Successfully updated access")
        return reverse_lazy("manage-datasource", kwargs={"pk": self.object.s3bucket.id})

    def form_valid(self, form):
        self.object.access_level = form.cleaned_data['access_level']
        self.object.is_admin = form.cleaned_data['is_admin']
        self.object.save()
        return FormMixin.form_valid(self, form)


class RevokeAccess(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = UserS3Bucket
    permission_required = 'api.destroy_users3bucket'

    def get_success_url(self):
        messages.success(self.request, "Successfully revoked access")
        return reverse_lazy("manage-datasource", kwargs={"pk": self.object.s3bucket.id})


class GrantAccess(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    form_class = GrantAccessForm
    model = UserS3Bucket
    permission_required = 'api.create_users3bucket'

    def get_form_kwargs(self):
        return FormMixin.get_form_kwargs(self)

    def get_success_url(self):
        messages.success(self.request, "Successfully granted access")
        return reverse_lazy("manage-datasource", kwargs={"pk": self.object.s3bucket.id})

    def form_valid(self, form):
        user = self.request.user
        bucket = get_object_or_404(S3Bucket, pk=self.kwargs['pk'])

        if not user.has_perm('api.grant_s3bucket_access', bucket):
            raise PermissionDenied()

        is_admin = form.cleaned_data['is_admin']

        if is_admin and not user.has_perm('api.add_s3bucket_admin', bucket):
            raise PermissionDenied()

        self.object = UserS3Bucket.objects.create(
            access_level=form.cleaned_data['access_level'],
            is_admin=is_admin,
            user_id=form.cleaned_data['user_id'],
            s3bucket_id=self.kwargs['pk'],
        )
        return FormMixin.form_valid(self, form)
