from django.contrib.auth.models import Group
from rest_framework import viewsets

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
    UserApp,
    UserS3Bucket,
)
from control_panel_api.permissions import (
    AppPermissions,
    S3BucketPermissions,
    UserPermissions,
)
from control_panel_api.serializers import (
    AppS3BucketSerializer,
    AppSerializer,
    UserAppSerializer,
    GroupSerializer,
    S3BucketSerializer,
    UserS3BucketSerializer,
    UserSerializer,
)


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    filter_backends = (UserFilter,)
    permission_classes = (UserPermissions,)

    def perform_create(self, serializer):
        instance = serializer.save()
        instance.aws_create_role()
        instance.helm_create()

    def perform_destroy(self, instance):
        instance.delete()
        instance.aws_delete_role()


class GroupViewSet(viewsets.ModelViewSet):
    queryset = Group.objects.all()
    serializer_class = GroupSerializer


class AppViewSet(viewsets.ModelViewSet):
    queryset = App.objects.all()
    serializer_class = AppSerializer
    filter_backends = (AppFilter,)

    filter_fields = ('name', 'repo_url', 'slug')
    permission_classes = (AppPermissions,)

    def perform_create(self, serializer):
        app = serializer.save(created_by=self.request.user)
        app.aws_create_role()

    def perform_destroy(self, instance):
        instance.delete()
        instance.aws_delete_role()


class AppS3BucketViewSet(viewsets.ModelViewSet):
    queryset = AppS3Bucket.objects.all()
    serializer_class = AppS3BucketSerializer

    def perform_create(self, serializer):
        apps3bucket = serializer.save()
        apps3bucket.aws_create()

    def perform_update(self, serializer):
        apps3bucket = serializer.save()
        apps3bucket.aws_update()

    def perform_destroy(self, instance):
        instance.delete()
        instance.aws_delete()


class UserS3BucketViewSet(viewsets.ModelViewSet):
    queryset = UserS3Bucket.objects.all()
    serializer_class = UserS3BucketSerializer

    def perform_create(self, serializer):
        instance = serializer.save()
        instance.aws_create()

    def perform_update(self, serializer):
        instance = serializer.save()
        instance.aws_update()

    def perform_destroy(self, instance):
        instance.delete()
        instance.aws_delete()


class S3BucketViewSet(viewsets.ModelViewSet):
    queryset = S3Bucket.objects.all()
    serializer_class = S3BucketSerializer
    filter_backends = (S3BucketFilter,)
    permission_classes = (S3BucketPermissions,)

    def perform_create(self, serializer):
        instance = serializer.save(created_by=self.request.user)
        instance.aws_create()
        instance.create_users3bucket(user=self.request.user)

    def perform_destroy(self, instance):
        instance.delete()
        instance.aws_delete()


class UserAppViewSet(viewsets.ModelViewSet):
    queryset = UserApp.objects.all()
    serializer_class = UserAppSerializer
