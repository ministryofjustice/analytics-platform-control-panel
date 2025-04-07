# Third-party
import structlog
from celery import shared_task

# First-party/Local
from controlpanel.api.auth0 import Auth0Error
from controlpanel.api.models.dashboard_domain import DashboardDomain
from controlpanel.api.models.dashboard_viewer import DashboardViewer

log = structlog.getLogger(__name__)


@shared_task(acks_on_failure_or_timeout=False)
def prune_dashboard_viewers():
    """
    Remove dashboard viewers that are not associated with any dashboards.
    This also checks that the viewer can still access dashboards if they
    have a valid domain. This will remove the auth0 role required to access
    the dashboard service.
    """
    domains = (
        DashboardDomain.objects.filter(dashboards__isnull=False)
        .distinct()
        .values_list("name", flat=True)
    )
    viewers = DashboardViewer.objects.filter(dashboards__isnull=True)
    for viewer in viewers:
        viewer_domain = viewer.email.split("@")[-1]
        if viewer_domain not in domains:
            try:
                viewer.delete()
            except Auth0Error:
                log.info(f"Failed to remove viewer {viewer.email} from Auth0")
