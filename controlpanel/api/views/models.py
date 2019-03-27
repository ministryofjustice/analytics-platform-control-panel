from django.contrib.auth.models import Group
from django.http import HttpResponseRedirect
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from controlpanel.api import (
    filters,
    permissions,
    serializers,
)
from controlpanel.api.elasticsearch import bucket_hits_aggregation
from controlpanel.api.models import (
    App,
    AppS3Bucket,
    S3Bucket,
    User,
    UserApp,
    UserS3Bucket,
)


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = serializers.UserSerializer
    filter_backends = (DjangoFilterBackend,)
    permission_classes = (permissions.UserPermissions,)

    def perform_create(self, serializer):
        instance = serializer.save()
        instance.aws_create_role()
        instance.helm_create()

    def perform_destroy(self, instance):
        instance.delete()
        instance.aws_delete_role()
        instance.helm_delete()


class GroupViewSet(viewsets.ModelViewSet):
    queryset = Group.objects.all()
    serializer_class = serializers.GroupSerializer


class AppViewSet(viewsets.ModelViewSet):
    queryset = App.objects.all()
    serializer_class = serializers.AppSerializer
    filter_backends = (DjangoFilterBackend,)
    permission_classes = (permissions.AppPermissions,)
    filterset_fields = ('name', 'repo_url', 'slug')

    def perform_create(self, serializer):
        app = serializer.save(created_by=self.request.user)
        app.aws_create_role()

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        if 'redirect_to' in request.query_params:
            return HttpResponseRedirect(
                redirect_to=request.query_params['redirect_to'],
            )
        return Response(status=status.HTTP_204_NO_CONTENT)

    def perform_destroy(self, instance):
        instance.delete()
        instance.aws_delete_role()


class AppS3BucketViewSet(viewsets.ModelViewSet):
    queryset = AppS3Bucket.objects.all()
    serializer_class = serializers.AppS3BucketSerializer

    def perform_create(self, serializer):
        apps3bucket = serializer.save()
        apps3bucket.aws_create()

    def perform_update(self, serializer):
        apps3bucket = serializer.save()
        apps3bucket.aws_update()


class UserS3BucketViewSet(viewsets.ModelViewSet):
    queryset = UserS3Bucket.objects.all()
    serializer_class = serializers.UserS3BucketSerializer
    filter_backends = (filters.UserS3BucketFilter,)
    permission_classes = (permissions.UserS3BucketPermissions,)

    def perform_create(self, serializer):
        instance = serializer.save()
        instance.aws_create()

    def perform_update(self, serializer):
        instance = serializer.save()
        instance.aws_update()


class S3BucketViewSet(viewsets.ModelViewSet):
    queryset = S3Bucket.objects.all()
    serializer_class = serializers.S3BucketSerializer
    filter_backends = (filters.S3BucketFilter,)
    permission_classes = (permissions.S3BucketPermissions,)
    filterset_fields = ('is_data_warehouse',)

    def perform_create(self, serializer):
        instance = serializer.save(created_by=self.request.user)
        instance.aws_create()
        instance.create_users3bucket(user=self.request.user)

    @action(detail=True)
    def access_logs(self, request, pk=None):
        num_days = request.query_params.get('num_days')
        if num_days:
            num_days = int(num_days)

        result = bucket_hits_aggregation(self.get_object().name, num_days)

        return Response(serializers.ESBucketHitsSerializer(result).data)


class UserAppViewSet(viewsets.ModelViewSet):
    queryset = UserApp.objects.all()
    serializer_class = serializers.UserAppSerializer
