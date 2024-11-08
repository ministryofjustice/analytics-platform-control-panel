# Third-party
from django.db.transaction import atomic
from django.http import HttpResponseRedirect
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

# First-party/Local
from controlpanel.api import filters, permissions, serializers
from controlpanel.api.elasticsearch import bucket_hits_aggregation
from controlpanel.api.models import App, AppS3Bucket, S3Bucket, User, UserApp, UserS3Bucket


class UserViewSet(viewsets.ModelViewSet):
    resource = "user"

    queryset = User.objects.all()
    serializer_class = serializers.UserSerializer
    filter_backends = (DjangoFilterBackend,)
    permission_classes = (permissions.UserPermissions | permissions.JWTTokenResourcePermissions,)


class AppViewSet(viewsets.ModelViewSet):
    resource = "app"

    serializer_class = serializers.AppSerializer
    filter_backends = (DjangoFilterBackend,)
    permission_classes = (permissions.AppPermissions | permissions.AppJwtTokenResourcePermissions,)
    filterset_fields = ("name", "repo_url", "slug")
    lookup_field = "res_id"

    def _skip_queryset_restriction(self):
        return self.request.user.is_superuser or (
            hasattr(self.request.user, "is_client") and self.request.user.is_client
        )

    def get_queryset(self):
        if self._skip_queryset_restriction():
            return App.objects.all()
        else:
            qs = App.objects.all().prefetch_related("userapps")
            return qs.filter(userapps__user=self.request.user)

    @atomic
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def destroy(self, request, *args, **kwargs):
        self.get_object().delete(github_api_token=self.request.user.github_api_token)
        if "redirect_to" in request.query_params:
            return HttpResponseRedirect(
                redirect_to=request.query_params["redirect_to"],
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


class AppS3BucketViewSet(viewsets.ModelViewSet):
    queryset = AppS3Bucket.objects.all()
    serializer_class = serializers.AppS3BucketSerializer
    permission_classes = (permissions.AppS3BucketPermissions,)
    filter_backends = (filters.AppS3BucketFilter,)


class UserS3BucketViewSet(viewsets.ModelViewSet):
    queryset = UserS3Bucket.objects.all()
    serializer_class = serializers.UserS3BucketSerializer
    filter_backends = (filters.UserS3BucketFilter,)
    permission_classes = (permissions.UserS3BucketPermissions,)


class S3BucketViewSet(viewsets.ModelViewSet):
    queryset = S3Bucket.objects.all()
    serializer_class = serializers.S3BucketSerializer
    filter_backends = (filters.S3BucketFilter,)
    permission_classes = (permissions.S3BucketPermissions,)
    filterset_fields = ("is_data_warehouse",)

    @atomic
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True)
    def access_logs(self, request, pk=None):
        num_days = request.query_params.get("num_days")
        if num_days:
            num_days = int(num_days)

        result = bucket_hits_aggregation(self.get_object().name, num_days)

        return Response(serializers.ESBucketHitsSerializer(result).data)


class UserAppViewSet(viewsets.ModelViewSet):
    queryset = UserApp.objects.all()
    serializer_class = serializers.UserAppSerializer
