from django.contrib.auth.models import Group
from rest_framework import viewsets
from rest_framework.exceptions import ValidationError

from control_panel_api import services
from control_panel_api.filters import (
    AppFilter,
    S3BucketFilter,
    UserFilter,
)
from control_panel_api.models import (
    App,
    AppS3Bucket,
    S3Bucket,
    User,
)
from control_panel_api.permissions import (
    AppPermissions,
    S3BucketPermissions,
    UserPermissions,
)
from control_panel_api.serializers import (
    AppS3BucketSerializer,
    AppSerializer,
    GroupSerializer,
    S3BucketSerializer,
    UserSerializer,
)


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    filter_backends = (UserFilter,)
    permission_classes = (UserPermissions,)


class GroupViewSet(viewsets.ModelViewSet):
    queryset = Group.objects.all()
    serializer_class = GroupSerializer


class AppViewSet(viewsets.ModelViewSet):
    queryset = App.objects.all()
    serializer_class = AppSerializer
    filter_backends = (AppFilter,)
    permission_classes = (AppPermissions,)

    def perform_create(self, serializer):
        app = serializer.save()
        app.create_app_role()

    def perform_destroy(self, instance):
        instance.delete()
        instance.delete_app_role()


class AppS3BucketViewSet(viewsets.ModelViewSet):
    queryset = AppS3Bucket.objects.all()
    serializer_class = AppS3BucketSerializer

    def perform_create(self, serializer):
        apps3bucket = serializer.save()
        services.apps3bucket_create(apps3bucket)

    def perform_update(self, serializer):
        apps3bucket = serializer.save()
        apps3bucket.update_aws_permissions()

    def perform_destroy(self, instance):
        instance.delete()
        services.apps3bucket_delete(instance)


class S3BucketViewSet(viewsets.ModelViewSet):
    queryset = S3Bucket.objects.all()
    serializer_class = S3BucketSerializer
    filter_backends = (S3BucketFilter,)
    permission_classes = (S3BucketPermissions,)

    def perform_create(self, serializer):
        instance = serializer.save()
        instance.aws_create()

    def perform_destroy(self, instance):
        instance.delete()
        instance.aws_delete()
