# Third-party
from rest_framework import mixins, viewsets

# First-party/Local
from controlpanel.api import permissions
from controlpanel.api.models import Tool
from controlpanel.api.serializers import ToolSerializer


class ToolViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    filter_backends = []
    model = Tool
    pagination_class = None
    permission_classes = (permissions.ToolPermissions,)
    serializer_class = ToolSerializer
