from rest_framework import mixins, status, viewsets
from rest_framework.response import Response

from controlpanel.api import permissions
from controlpanel.api.serializers import (
    ToolSerializer,
    ToolDeploymentSerializer
)
from controlpanel.api.tools import (
    SUPPORTED_TOOL_NAMES,
    Tool,
    ToolDeployment,
)


class ToolViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    permission_classes = (permissions.ToolDeploymentPermissions,)
    queryset = [{"name": n} for n in SUPPORTED_TOOL_NAMES]
    filter_backends = []
    serializer_class = ToolSerializer
    pagination_class = None


class ToolDeploymentViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    permission_classes = (permissions.ToolDeploymentPermissions,)
    serializer_class = ToolDeploymentSerializer
    filter_backends = []
    pagination_class = None

    def create(self, request):
        tool = Tool.create(request.data["name"])
        tool.deploy_for(request.user)
        return Response({}, status=status.HTTP_201_CREATED)

    def get_queryset(self):
        return ToolDeployment.list(self.request.user)
