# Third-party
from django.conf import settings
from django.db.models import Q
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

# First-party/Local
from controlpanel.api import permissions
from controlpanel.api.aws import AWSQuicksight
from controlpanel.api.models.dashboard import Dashboard
from controlpanel.api.serializers import DashboardSerializer
from controlpanel.utils import get_domain_from_email


class DashboardViewSet(ViewSet):
    """
    A ViewSet for managing dashboards.
    """

    permission_classes = [permissions.IsSuperuser]
    lookup_field = "quicksight_id"

    @action(detail=False, methods=["get"])
    def dashboard_list(self, request):
        """
        Get a list of dashboards that the viewer has access to.
        """
        viewer_email = request.query_params.get("email")

        if not viewer_email:
            return Response({"error": "Email parameter is required."}, status=400)

        domain = get_domain_from_email(viewer_email)

        dashboards = Dashboard.objects.filter(
            Q(viewers__email=viewer_email) | Q(whitelist_domains__name=domain)
        ).distinct()

        serialiser = DashboardSerializer(dashboards, many=True)
        return Response(serialiser.data)

    @action(detail=True, methods=["get"])
    def embed_url(self, request, quicksight_id=None):
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

            assume_role_name = settings.QUICKSIGHT_ASSUMED_ROLE
            quicksight_region = settings.QUICKSIGHT_ACCOUNT_REGION
            quicksight_client = AWSQuicksight(
                assume_role_name=assume_role_name,
                profile_name="control_panel_api",
                region_name=quicksight_region,
            )

            response = quicksight_client.generate_embed_url_for_anonymous_user(
                dashboard_arn=dashboard.arn, dashboard_id=quicksight_id
            )

            return Response(
                {
                    "embed_url": response["EmbedUrl"],
                    "anonymous_user_arn": response["AnonymousUserArn"],
                }
            )
        except Dashboard.DoesNotExist:
            return Response({"error": "Dashboard not found."}, status=404)
