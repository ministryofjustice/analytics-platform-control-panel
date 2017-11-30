import logging
from subprocess import CalledProcessError

from botocore.exceptions import ClientError
from django.contrib.auth.models import Group
from django.db import transaction
from django.views.decorators.csrf import csrf_exempt
from rest_framework import viewsets
from rest_framework.decorators import api_view, permission_classes

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
    K8sPermissions,
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
import k8s

logger = logging.getLogger(__name__)


def handle_external_exceptions(func):
    """Decorates a view function that calls aws or helm to catch exceptions and
    throw an APIException derived error
    """

    def inner(*args, **kwargs):
        try:
            func(*args, **kwargs)
        except ClientError as e:
            logger.error(e)
            raise AWSException(e) from e
        except CalledProcessError as e:
            logger.error(e)
            raise HelmException(e) from e

    return inner


@api_view(['DELETE', 'GET', 'HEAD', 'OPTIONS', 'PATCH', 'POST', 'PUT'])
@permission_classes((K8sPermissions,))
@csrf_exempt
def k8s_api_handler(request):
    return k8s.proxy(request)


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    filter_backends = (UserFilter,)
    permission_classes = (UserPermissions,)

    @handle_external_exceptions
    @transaction.atomic
    def perform_create(self, serializer):
        instance = serializer.save()

        instance.aws_create_role()
        instance.helm_create()

    @handle_external_exceptions
    @transaction.atomic
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

    @handle_external_exceptions
    @transaction.atomic
    def perform_create(self, serializer):
        app = serializer.save(created_by=self.request.user)

        app.aws_create_role()

    @handle_external_exceptions
    @transaction.atomic
    def perform_destroy(self, instance):
        instance.delete()

        instance.aws_delete_role()


class AppS3BucketViewSet(viewsets.ModelViewSet):
    queryset = AppS3Bucket.objects.all()
    serializer_class = AppS3BucketSerializer

    @handle_external_exceptions
    @transaction.atomic
    def perform_create(self, serializer):
        apps3bucket = serializer.save()

        apps3bucket.aws_create()

    @handle_external_exceptions
    @transaction.atomic
    def perform_update(self, serializer):
        apps3bucket = serializer.save()

        apps3bucket.aws_update()

    @handle_external_exceptions
    @transaction.atomic
    def perform_destroy(self, instance):
        instance.delete()

        instance.aws_delete()


class UserS3BucketViewSet(viewsets.ModelViewSet):
    queryset = UserS3Bucket.objects.all()
    serializer_class = UserS3BucketSerializer

    @handle_external_exceptions
    @transaction.atomic
    def perform_create(self, serializer):
        instance = serializer.save()

        instance.aws_create()

    @handle_external_exceptions
    @transaction.atomic
    def perform_update(self, serializer):
        instance = serializer.save()

        instance.aws_update()

    @handle_external_exceptions
    @transaction.atomic
    def perform_destroy(self, instance):
        instance.delete()

        instance.aws_delete()


class S3BucketViewSet(viewsets.ModelViewSet):
    queryset = S3Bucket.objects.all()
    serializer_class = S3BucketSerializer
    filter_backends = (S3BucketFilter,)
    permission_classes = (S3BucketPermissions,)

    @handle_external_exceptions
    @transaction.atomic
    def perform_create(self, serializer):
        instance = serializer.save(created_by=self.request.user)

        instance.aws_create()

        instance.create_users3bucket(user=self.request.user)

    @handle_external_exceptions
    @transaction.atomic
    def perform_destroy(self, instance):
        instance.delete()

        instance.aws_delete()


class UserAppViewSet(viewsets.ModelViewSet):
    queryset = UserApp.objects.all()
    serializer_class = UserAppSerializer
