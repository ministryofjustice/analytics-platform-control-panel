from rest_framework import status, viewsets
from rest_framework.response import Response

from controlpanel.api import permissions
from controlpanel.api.tools import (
    SUPPORTED_TOOL_NAMES,
    Tool,
    ToolDeployment,
)


class ToolViewSet(viewsets.ViewSet):
    permission_classes = (permissions.ToolDeploymentPermissions,)

    def list(self, request):
        return Response([{"name": n} for n in SUPPORTED_TOOL_NAMES])


class ToolDeploymentViewSet(viewsets.ViewSet):
    permission_classes = (permissions.ToolDeploymentPermissions,)

    def create(self, request):
        tool = Tool.create(request.data["name"])
        tool.deploy_for(request.user)
        return Response({}, status=status.HTTP_201_CREATED)

    def list(self, request):
        return Response(ToolDeployment.list(request.user))
