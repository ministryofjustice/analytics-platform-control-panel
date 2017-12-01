import logging
from subprocess import CalledProcessError

from botocore.exceptions import ClientError
from django.contrib.auth.models import Group
from django.db import transaction
from rest_framework import viewsets

from control_panel_api.exceptions import (
    AWSException,
    HelmException,
)
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
    GroupSerializer,
    S3BucketSerializer,
    UserAppSerializer,
    UserS3BucketSerializer,
    UserSerializer,
)

logger = logging.getLogger(__name__)


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    filter_backends = (UserFilter,)
    permission_classes = (UserPermissions,)

    @transaction.atomic
    def perform_create(self, serializer):
        instance = serializer.save()

        try:
            instance.aws_create_role()
            instance.helm_create()
        except ClientError as e:
            logger.error(e)
            raise AWSException(e) from e
        except CalledProcessError as e:
            logger.error(e)
            raise HelmException(e) from e

    @transaction.atomic
    def perform_destroy(self, instance):
        instance.delete()

        try:
            instance.aws_delete_role()
        except ClientError as e:
            logger.error(e)
            raise AWSException(e) from e


class GroupViewSet(viewsets.ModelViewSet):
    queryset = Group.objects.all()
    serializer_class = GroupSerializer


class AppViewSet(viewsets.ModelViewSet):
    queryset = App.objects.all()
    serializer_class = AppSerializer
    filter_backends = (AppFilter,)

    filter_fields = ('name', 'repo_url', 'slug')
    permission_classes = (AppPermissions,)

    @transaction.atomic
    def perform_create(self, serializer):
        app = serializer.save(created_by=self.request.user)

        try:
            app.aws_create_role()
        except ClientError as e:
            logger.error(e)
            raise AWSException(e) from e

    @transaction.atomic
    def perform_destroy(self, instance):
        instance.delete()

        try:
            instance.aws_delete_role()
        except ClientError as e:
            logger.error(e)
            raise AWSException(e) from e


class AppS3BucketViewSet(viewsets.ModelViewSet):
    queryset = AppS3Bucket.objects.all()
    serializer_class = AppS3BucketSerializer

    @transaction.atomic
    def perform_create(self, serializer):
        apps3bucket = serializer.save()

        try:
            apps3bucket.aws_create()
        except ClientError as e:
            logger.error(e)
            raise AWSException(e) from e

    @transaction.atomic
    def perform_update(self, serializer):
        apps3bucket = serializer.save()

        try:
            apps3bucket.aws_update()
        except ClientError as e:
            logger.error(e)
            raise AWSException(e) from e

    @transaction.atomic
    def perform_destroy(self, instance):
        instance.delete()

        try:
            instance.aws_delete()
        except ClientError as e:
            logger.error(e)
            raise AWSException(e) from e


class UserS3BucketViewSet(viewsets.ModelViewSet):
    queryset = UserS3Bucket.objects.all()
    serializer_class = UserS3BucketSerializer

    @transaction.atomic
    def perform_create(self, serializer):
        instance = serializer.save()

        try:
            instance.aws_create()
        except ClientError as e:
            logger.error(e)
            raise AWSException from e

    @transaction.atomic
    def perform_update(self, serializer):
        instance = serializer.save()

        try:
            instance.aws_update()
        except ClientError as e:
            logger.error(e)
            raise AWSException(e) from e

    @transaction.atomic
    def perform_destroy(self, instance):
        instance.delete()

        try:
            instance.aws_delete()
        except ClientError as e:
            logger.error(e)
            raise AWSException(e) from e


class S3BucketViewSet(viewsets.ModelViewSet):
    queryset = S3Bucket.objects.all()
    serializer_class = S3BucketSerializer
    filter_backends = (S3BucketFilter,)
    permission_classes = (S3BucketPermissions,)

    @transaction.atomic
    def perform_create(self, serializer):
        instance = serializer.save(created_by=self.request.user)

        try:
            instance.aws_create()
        except ClientError as e:
            logger.error(e)
            raise AWSException(e) from e

        instance.create_users3bucket(user=self.request.user)

    @transaction.atomic
    def perform_destroy(self, instance):
        instance.delete()

        try:
            instance.aws_delete()
        except ClientError as e:
            logger.error(e)
            raise AWSException(e) from e


class UserAppViewSet(viewsets.ModelViewSet):
    queryset = UserApp.objects.all()
    serializer_class = UserAppSerializer
