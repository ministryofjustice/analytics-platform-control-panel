from rest_framework import viewsets, mixins
from django_filters.rest_framework import DjangoFilterBackend

from controlpanel.api.models import App
from controlpanel.api import (
    permissions,
    serializers,
)


class AppByNameViewSet(mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    resource = "app"

    queryset = App.objects.all()

    serializer_class = serializers.AppSerializer
    permission_classes = (permissions.AppPermissions | permissions.JWTTokenResourcePermissions,)
    filter_backends = (DjangoFilterBackend,)
    http_method_names = ['get']
    lookup_field = "name"
