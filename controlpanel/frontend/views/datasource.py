from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic.base import ContextMixin
from django.views.generic.detail import DetailView
from django.views.generic.list import ListView

from controlpanel.api.models import (
    User,
    UserS3Bucket,
)


class DatasourceTypeMixin(ContextMixin):
    datasource_type = None

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context['datasource_type'] = self.datasource_type
        return context


class WarehouseMixin(DatasourceTypeMixin):
    datasource_type = "warehouse"


class WebappMixin(DatasourceTypeMixin):
    datasource_type = "webapp"


class BucketList(LoginRequiredMixin, DatasourceTypeMixin, ListView):
    template_name = "datasource-list.html"

    def get_queryset(self):
        return self.request.user.users3buckets.filter(
            s3bucket__is_data_warehouse=self.datasource_type == 'warehouse',
        )


class WarehouseData(WarehouseMixin, BucketList):
    pass


class WebappData(WebappMixin, BucketList):
    pass


class BucketDetail(LoginRequiredMixin, DatasourceTypeMixin, DetailView):
    model = UserS3Bucket
    template_name = "datasource-detail.html"

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        bucket = self.get_object()
        bucket_users = [ub.user for ub in bucket.s3bucket.users3buckets.all()]
        bucket_user_ids = [user.auth0_id for user in bucket_users]
        context['users_options'] = User.objects.exclude(
            auth0_id__isnull=True,
            auth0_id__in=bucket_user_ids,
        )
        return context


class WarehouseBucketDetail(WarehouseMixin, BucketDetail):
    pass


class WebappBucketDetail(WebappMixin, BucketDetail):
    pass
