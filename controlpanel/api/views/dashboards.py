# Third-party
from django.db.models import Q
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

# First-party/Local
from controlpanel.api import permissions
from controlpanel.api.models.dashboard import Dashboard
from controlpanel.api.pagination import CustomPageNumberPagination
from controlpanel.api.serializers import DashboardSerializer, DashboardUrlSerializer
from controlpanel.utils import get_domain_from_email


class DashboardViewSet(ViewSet):
    """
    A ViewSet for managing dashboards.
    """

    permission_classes = [permissions.IsSuperuser]
    lookup_field = "quicksight_id"

    def list(self, request):
        """
        Get a paginated list of dashboards that the viewer has access to.
        """
        viewer_email = request.query_params.get("email")

        if not viewer_email:
            return Response({"error": "Email parameter is required."}, status=400)

        domain = get_domain_from_email(viewer_email)

        dashboards = Dashboard.objects.filter(
            Q(viewers__email=viewer_email) | Q(whitelist_domains__name=domain)
        ).distinct()

        paginator = CustomPageNumberPagination()
        paginated_dashboards = paginator.paginate_queryset(dashboards, request)
        serializer = DashboardSerializer(paginated_dashboards, many=True)

        return paginator.get_paginated_response(serializer.data)

    def retrieve(self, request, quicksight_id=None):
        """
        Get a dashboard by its QuickSight ID.
        """
        try:
            viewer_email = request.query_params.get("email")

            if not viewer_email:
                return Response({"error": "Email parameter is required."}, status=400)

            domain = get_domain_from_email(viewer_email)

            # Query using the unique `quicksight_id` field
            dashboard = Dashboard.objects.filter(
                Q(quicksight_id=quicksight_id)
                & (Q(viewers__email=viewer_email) | Q(whitelist_domains__name=domain))
            ).first()

            if not dashboard:
                return Response(
                    {"error": f"Dashboard {quicksight_id} not found."},
                    status=404,
                )

            serialiser = DashboardUrlSerializer(dashboard)
            return Response(serialiser.data)
        except Dashboard.DoesNotExist:
            return Response({"error": "Dashboard not found."}, status=404)
