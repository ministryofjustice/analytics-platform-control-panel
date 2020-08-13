from rest_framework import mixins, status, viewsets
from rest_framework.response import Response

from controlpanel.api import permissions
from controlpanel.api.serializers import (
    ToolSerializer,
)
from controlpanel.api.models import (
    Tool,
    ToolDeployment,
)


class ToolViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    filter_backends = []
    model = Tool
    pagination_class = None
    permission_classes = (permissions.ToolPermissions,)
    serializer_class = ToolSerializer
