# Third-party
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import mixins, viewsets

# First-party/Local
from controlpanel.api import permissions, serializers
from controlpanel.api.models import App


class AppByNameViewSet(mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    resource = "app"

    queryset = App.objects.all()

    serializer_class = serializers.AppSerializer
    permission_classes = (permissions.AppPermissions | permissions.JWTTokenResourcePermissions,)
    filter_backends = (DjangoFilterBackend,)
    http_method_names = ["get"]
    lookup_field = "name"
