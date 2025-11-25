# Third-party
import structlog
from django.db.models import Q
from rest_framework.response import Response
from rest_framework.viewsets import ReadOnlyModelViewSet

# First-party/Local
from controlpanel.api import permissions
from controlpanel.api.filters import DashboardFilter
from controlpanel.api.models.dashboard import Dashboard
from controlpanel.api.pagination import DashboardPaginator
from controlpanel.api.serializers import DashboardSerializer, DashboardUrlSerializer
from controlpanel.utils import get_domain_from_email

log = structlog.getLogger(__name__)


class DashboardViewSet(ReadOnlyModelViewSet):
    """
    A ViewSet for managing dashboards.
    """

    queryset = Dashboard.objects.all().order_by("name")
    serializer_class = DashboardSerializer
    resource = "dashboard"
    permission_classes = [permissions.IsSuperuser | permissions.JWTTokenResourcePermissions]
    lookup_field = "quicksight_id"
    pagination_class = DashboardPaginator
    filter_backends = (DashboardFilter,)

    def get_object(self):
        """
        Retrieve a single dashboard by its QuickSight ID and check access for the viewer.
        """
        quicksight_id = self.kwargs.get(self.lookup_field)
        viewer_email = self.request.query_params.get("email")

        if not viewer_email:
            raise ValueError("Email parameter is required.")

        domain = get_domain_from_email(viewer_email)

        dashboard = Dashboard.objects.filter(
            Q(quicksight_id=quicksight_id)
            & (Q(viewers__email=viewer_email) | Q(whitelist_domains__name=domain))
        ).first()

        if not dashboard:
            raise Dashboard.DoesNotExist(f"Dashboard {quicksight_id} not found.")

        return dashboard

    def list(self, request, *args, **kwargs):
        """
        Get a paginated list of dashboards that the viewer has access to.
        """
        if not request.query_params.get("email"):
            return Response({"error": "Email parameter is required."}, status=400)

        try:
            return super().list(request, *args, **kwargs)
        except ValueError as e:
            return Response({"error": str(e)}, status=400)

    def retrieve(self, request, *args, **kwargs):
        """
        Get a dashboard by its QuickSight ID.
        """
        try:
            dashboard = self.get_object()
            serializer = DashboardUrlSerializer(dashboard)
            log.info(
                f"{dashboard.name} requested by {request.query_params.get('email')}",
                audit="dashboard_audit",
            )
            return Response(serializer.data)
        except ValueError as e:
            return Response({"error": str(e)}, status=400)
        except Dashboard.DoesNotExist as e:
            return Response({"error": str(e)}, status=404)
