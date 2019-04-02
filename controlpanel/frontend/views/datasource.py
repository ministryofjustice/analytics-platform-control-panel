from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic.base import ContextMixin
from django.views.generic.detail import DetailView
from django.views.generic.list import ListView

from controlpanel.api.models import (
    S3Bucket,
    User,
)


class DatasourceMixin(ContextMixin):
    all_datasources = True
    datasource_type = None

    def get_datasource_type(self):
        if self.datasource_type is None:
            if hasattr(self, 'object'):
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
        context['users_options'] = User.objects.exclude(
            auth0_id__isnull=True,
            auth0_id__in=member_ids,
        )
        return context
