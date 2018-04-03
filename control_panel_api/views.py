import logging
from subprocess import CalledProcessError

from botocore.exceptions import ClientError
from django.contrib.auth.models import Group
from django.db import transaction
from django.http import JsonResponse
from django.http.response import Http404
from django.views.decorators.csrf import csrf_exempt
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response

from control_panel_api.auth0 import Auth0
from control_panel_api.exceptions import (
    AWSException,
    HelmException,
)
from control_panel_api.filters import (
    AppFilter,
    S3BucketFilter,
    UserS3BucketFilter,
)
from control_panel_api.k8s import proxy as k8s_proxy
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
    IsSuperuser,
    K8sPermissions,
    S3BucketPermissions,
    ToolDeploymentPermissions,
    UserPermissions,
    UserS3BucketPermissions,
)
from control_panel_api.serializers import (
    AppCustomerSerializer,
    AppS3BucketSerializer,
    AppSerializer,
    GroupSerializer,
    S3BucketSerializer,
    UserAppSerializer,
    UserS3BucketSerializer,
    UserSerializer,
)
from control_panel_api.tools import Tool

logger = logging.getLogger(__name__)


def handle_external_exceptions(func):
    """Decorates a view function that calls aws or helm to catch exceptions and
    throw an APIException derived error
    """

    def inner(*args, **kwargs):
        try:
            return func(*args, **kwargs)
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
    return k8s_proxy(request)


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    filter_backends = (DjangoFilterBackend,)
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
        instance.helm_delete()


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


class AppCustomersAPIView(GenericAPIView):
    queryset = App.objects.all()
    serializer_class = AppCustomerSerializer
    permission_classes = (IsSuperuser,)

    def get(self, request, *args, **kwargs):
        instance = self.get_object()

        members = Auth0().get_group_members(instance.name)

        if members is None:
            raise Http404

        serializer = self.get_serializer(data=members, many=True)
        serializer.is_valid()

        return Response(serializer.data)

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        Auth0().add_group_member(
            self.get_object().name,
            serializer.validated_data['email']
        )

        return Response(serializer.data, status=status.HTTP_201_CREATED)


class AppCustomersDetailAPIView(GenericAPIView):
    queryset = App.objects.all()
    permission_classes = (IsSuperuser,)

    def delete(self, request, *args, **kwargs):
        Auth0().delete_group_member(self.get_object().name, kwargs['user_id'])

        return Response(status=status.HTTP_204_NO_CONTENT)


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
    filter_backends = (UserS3BucketFilter,)
    permission_classes = (UserS3BucketPermissions,)

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
    filter_fields = ('is_data_warehouse',)

    @handle_external_exceptions
    @transaction.atomic
    def perform_create(self, serializer):
        instance = serializer.save(created_by=self.request.user)

        instance.aws_create()

        instance.create_users3bucket(user=self.request.user)


class UserAppViewSet(viewsets.ModelViewSet):
    queryset = UserApp.objects.all()
    serializer_class = UserAppSerializer


@api_view(['POST'])
@permission_classes((ToolDeploymentPermissions,))
@handle_external_exceptions
def tool_deployments_list(request, tool_name):
    tool = Tool(tool_name)
    tool.deploy_for(request.user)

    return JsonResponse({}, status=status.HTTP_201_CREATED)
