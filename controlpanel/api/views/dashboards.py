# Third-party
import structlog
from rest_framework.response import Response
from rest_framework.viewsets import ReadOnlyModelViewSet

# First-party/Local
from controlpanel.api import permissions
from controlpanel.api.filters import DashboardFilter
from controlpanel.api.models.dashboard import Dashboard
from controlpanel.api.pagination import DashboardPaginator
from controlpanel.api.serializers import DashboardDetailSerializer, DashboardListSerializer

log = structlog.getLogger(__name__)


class DashboardViewSet(ReadOnlyModelViewSet):
    """
    A ViewSet for managing dashboards.
    """

    queryset = Dashboard.objects.all().order_by("name")
    serializer_class = DashboardListSerializer
    resource = "dashboard"
    permission_classes = [permissions.IsSuperuser | permissions.JWTTokenResourcePermissions]
    lookup_field = "quicksight_id"
    pagination_class = DashboardPaginator
    filter_backends = (DashboardFilter,)

    def get_serializer_class(self):
        if self.action == "retrieve":
            return DashboardDetailSerializer
        return DashboardListSerializer

    def retrieve(self, request, *args, **kwargs):
        """
        Require an email, even when viewing as a superuser, as the response includes fields that are
        specific to a user.
        """
        if not request.query_params.get("email"):
            return Response({"error": "Email query parameter is required."}, status=400)
        response = super().retrieve(request, *args, **kwargs)
        dashboard_name = response.data["name"]
        log.info(
            f"{dashboard_name} requested by {request.query_params.get('email')}",
            audit="dashboard_audit",
        )
        return response
