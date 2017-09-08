from django.contrib.auth.models import Group
from rest_framework import viewsets

from control_panel_api import services
from control_panel_api.filters import (
    AppFilter,
    S3BucketFilter,
    UserFilter,
)
from control_panel_api.models import (
    App,
    S3Bucket,
    User,
)
from control_panel_api.permissions import (
    AppPermissions,
    S3BucketPermissions,
    UserPermissions,
)
from control_panel_api.serializers import (
    GroupSerializer,
    AppSerializer,
    S3BucketSerializer,
    UserSerializer,
)


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    filter_backends = (UserFilter,)
    permission_classes = (UserPermissions, )


class GroupViewSet(viewsets.ModelViewSet):
    queryset = Group.objects.all()
    serializer_class = GroupSerializer


class AppViewSet(viewsets.ModelViewSet):
    queryset = App.objects.all()
    serializer_class = AppSerializer
    filter_backends = (AppFilter,)
    permission_classes = (AppPermissions, )


class S3BucketViewSet(viewsets.ModelViewSet):
    queryset = S3Bucket.objects.all()
    serializer_class = S3BucketSerializer
    filter_backends = (S3BucketFilter,)
    permission_classes = (S3BucketPermissions, )

    def perform_create(self, serializer):
        instance = serializer.save()
        services.create_bucket(instance.name)
        services.create_bucket_policies(instance.name)
