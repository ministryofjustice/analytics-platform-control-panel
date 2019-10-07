from rest_framework import mixins, status, viewsets
from rest_framework.response import Response

from controlpanel.api import permissions
from controlpanel.api.serializers import (
    ToolSerializer,
    ToolDeploymentSerializer
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


class ToolDeploymentViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    permission_classes = (permissions.ToolDeploymentPermissions,)
    serializer_class = ToolDeploymentSerializer
    filter_backends = []
    pagination_class = None

    def create(self, request):
        try:
            tool = Tool.objects.get(chart_name=request.data["name"])
        except Tool.DoesNotExist:
            return Response({}, status=status.HTTP_400_BAD_REQUEST)
        tool_deployment = ToolDeployment(tool, request.user)
        tool_deployment.save()
        return Response({}, status=status.HTTP_201_CREATED)

    def get_queryset(self):
        user = self.request.user
        id_token = user.get_id_token()
        return ToolDeployment.objects.filter(
            user=user,
            id_token=id_token,
        )
