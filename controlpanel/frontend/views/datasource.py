from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
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

    def get_datasource_type(self):
        if self.datasource_type is None:
            if hasattr(self, 'object') and self.object:
                if self.object.is_data_warehouse:
                    return "warehouse"
                return "webapp"
            return None
        return self.datasource_type

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context['all-datasources'] = self.all_datasources
        context['datasource_type'] = self.get_datasource_type()
        return context


class BucketList(LoginRequiredMixin, DatasourceMixin, ListView):
    model = S3Bucket
    template_name = "datasource-list.html"

    def get_queryset(self):
        return S3Bucket.objects.prefetch_related('users3buckets').all()


class WarehouseData(BucketList):
    all_datasources = False
    datasource_type = "warehouse"

    def get_queryset(self):
        return S3Bucket.objects.prefetch_related('users3buckets').filter(
            is_data_warehouse=True,
            users3buckets__user=self.request.user,
        )


class WebappData(BucketList):
    all_datasources = False
    datasource_type = "webapp"

    def get_queryset(self):
        return S3Bucket.objects.prefetch_related('users3buckets').filter(
            is_data_warehouse=False,
            users3buckets__user=self.request.user,
        )


class BucketDetail(LoginRequiredMixin, DatasourceMixin, DetailView):
    model = S3Bucket
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


class CreateDatasource(LoginRequiredMixin, DatasourceMixin, CreateView):
    form_class = CreateDatasourceForm
    model = S3Bucket
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
        messages.success(
            self.request,
            f"Successfully created {name} {datasource_type} data source",
        )
        return FormMixin.form_valid(self, form)


class DeleteDatasource(LoginRequiredMixin, DeleteView):
    model = S3Bucket

    def get_success_url(self):
        messages.success(self.request, "Successfully delete data source")
        return reverse_lazy("list-all-datasources")


class UpdateAccessLevel(LoginRequiredMixin, UpdateView):
    model = UserS3Bucket
    form_class = GrantAccessForm
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


class RevokeAccess(LoginRequiredMixin, DeleteView):
    model = UserS3Bucket

    def get_success_url(self):
        messages.success(self.request, "Successfully revoked access")
        return reverse_lazy("manage-datasource", kwargs={"pk": self.object.s3bucket.id})


class GrantAccess(LoginRequiredMixin, CreateView):
    form_class = GrantAccessForm
    model = UserS3Bucket

    def get_form_kwargs(self):
        return FormMixin.get_form_kwargs(self)

    def get_success_url(self):
        messages.success(self.request, "Successfully granted access")
        return reverse_lazy("manage-datasource", kwargs={"pk": self.object.s3bucket.id})

    def form_valid(self, form):
        self.object = UserS3Bucket.objects.create(
            access_level=form.cleaned_data['access_level'],
            is_admin=form.cleaned_data['is_admin'],
            user_id=form.cleaned_data['user_id'],
            s3bucket_id=self.kwargs['pk'],
        )
        return FormMixin.form_valid(self, form)
