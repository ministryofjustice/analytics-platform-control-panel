# Standard library
from unittest.mock import patch

# Third-party
import pytest
from model_bakery import baker

# First-party/Local
from controlpanel.api import helm
from controlpanel.api.models import (
    Dashboard,
    DashboardDomain,
    DashboardViewer,
    DashboardViewerAccess,
)
from controlpanel.api.tasks.dashboards import prune_dashboard_viewers


@pytest.fixture()
def ExtendedAuth0():
    with patch("controlpanel.api.auth0.ExtendedAuth0") as ExtendedAuth0:
        ExtendedAuth0.return_value.add_dashboard_member_by_email.return_value = None
        ExtendedAuth0.return_value.remove_dashboard_role.return_value = None
        yield ExtendedAuth0.return_value


@pytest.fixture
def dashboards(ExtendedAuth0):
    dashboards = []
    dashboards.append(
        baker.make(
            Dashboard,
            name="test-dashboard-1",
            quicksight_id="abc-123",
        )
    )

    dashboards.append(
        baker.make(
            Dashboard,
            name="test-dashboard-2",
            quicksight_id="def-456",
        )
    )

    dashboards.append(
        baker.make(
            Dashboard,
            name="test-dashboard-3",
            quicksight_id="ghi-789",
        )
    )

    return dashboards


@pytest.fixture
def viewers(dashboards):
    num_viewers = 4

    viewers = []
    domains = [
        "test-domain1.gov.uk",
        "test-domain2.gov.uk",
        "test-domain3.gov.uk",
        "test-domain4.gov.uk",
    ]

    for i in range(num_viewers):
        viewers.append(baker.make(DashboardViewer, email=f"test.user{i + 1}@{domains[i]}"))

    # only assign 2 so we can check that a user won't be pruned
    # if their domain is linked to a dashboard
    DashboardViewerAccess.objects.create(dashboard=dashboards[0], viewer=viewers[0])
    DashboardViewerAccess.objects.create(dashboard=dashboards[1], viewer=viewers[1])

    return viewers


@pytest.fixture
def domain(dashboards):
    num_domains = 3

    domains = []

    for i in range(num_domains):
        domains.append(baker.make(DashboardDomain, name=f"test-domain{i + 1}.gov.uk"))

    dashboards[0].whitelist_domains.add(domains[0])
    dashboards[1].whitelist_domains.add(domains[2])

    return domains


@pytest.mark.django_db
def test_prune_dashboard_viewers(ExtendedAuth0, dashboards, viewers, domain):
    """
    Test that the fourth viewer is removed as they are not assigned to a dashboard
    and their domain isn't linked to any dashboard.

    Viewer 1 is linked directly and via domain
    Viewer 2 is linked directly
    Viewer 3 is linked via domain
    Viewer 4 is not linked at all
    """
    prune_dashboard_viewers()
    assert ExtendedAuth0.remove_dashboard_role.call_count == 1
    assert DashboardViewer.objects.count() == 3
    assert DashboardViewer.objects.filter(email=viewers[3].email).exists() is False
