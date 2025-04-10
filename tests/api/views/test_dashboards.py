# Standard library
from unittest.mock import patch

# Third-party
import pytest
from django.urls import reverse
from model_bakery import baker
from rest_framework import status

NUM_DASHBOARDS = 3


@pytest.fixture()
def ExtendedAuth0():
    with patch("controlpanel.api.auth0.ExtendedAuth0") as ExtendedAuth0:
        ExtendedAuth0.return_value.add_dashboard_member_by_email.return_value = None
        yield ExtendedAuth0.return_value


@pytest.fixture(autouse=True)
def enable_db_for_all_tests(db):
    pass


@pytest.fixture
def users(users):
    users.update(
        {
            "dashboard_admin": baker.make(
                "api.User",
                auth0_id="github|dashboard-admin",
                username="dashboard_admin",
                justice_email="dashboard.admin@justice.gov.uk",
            ),
        }
    )
    return users


@pytest.fixture
def dashboard(users, ExtendedAuth0):
    baker.make("api.Dashboard", NUM_DASHBOARDS - 1)
    dashboard = baker.make(
        "api.Dashboard",
        name="test-dashboard",
        quicksight_id="abc-123",
        created_by=users["dashboard_admin"],
    )

    dashboard.admins.add(users["dashboard_admin"])
    return dashboard


@pytest.fixture
def dashboard_viewer(users, dashboard):
    viewer = baker.make("api.DashboardViewer", email=users["dashboard_admin"].justice_email)
    dashboard.viewers.add(viewer)
    return viewer


@pytest.fixture
def dashboard_domain(dashboard):
    domain = baker.make("api.DashboardDomain", name="justice.gov.uk")
    dashboard.whitelist_domains.add(domain)
    return domain


@pytest.mark.parametrize(
    "email, expected_status, expected_count",
    [
        ("dashboard.admin@justice.gov.uk", status.HTTP_200_OK, 1),
        ("domain.viewer@justice.gov.uk", status.HTTP_200_OK, 1),
        ("no.access@test.gov.uk", status.HTTP_200_OK, 0),
        (None, status.HTTP_400_BAD_REQUEST, 0),
    ],
)
def test_list(
    client, dashboard, dashboard_viewer, dashboard_domain, email, expected_status, expected_count
):
    data = {"email": email} if email else {}
    response = client.get(reverse("dashboard-list"), data=data)

    assert response.status_code == expected_status

    if expected_status == status.HTTP_200_OK:
        assert response.data["count"] == expected_count

        if expected_count > 0:
            result = response.data["results"][0]
            assert result["quicksight_id"] == dashboard.quicksight_id
            assert result["name"] == dashboard.name


@pytest.mark.parametrize(
    "email, embed_url, user_arn, expected_status",
    [
        (
            "dashboard.admin@justice.gov.uk",
            "https://quicksight-embed-url-viewer",
            "some:viewer:arn",
            status.HTTP_200_OK,
        ),
        (
            "domain.viewer@justice.gov.uk",
            "https://quicksight-embed-url-domain",
            "some:domain:arn",
            status.HTTP_200_OK,
        ),
        ("no.access@test.gov.uk", "", "", status.HTTP_404_NOT_FOUND),
        ("", "", "", status.HTTP_400_BAD_REQUEST),
    ],
)
def test_retrieve(
    client,
    dashboard,
    dashboard_viewer,
    dashboard_domain,
    email,
    embed_url,
    user_arn,
    expected_status,
):

    with patch("controlpanel.api.models.dashboard.Dashboard.get_embed_url") as get_embed_url:
        get_embed_url.return_value = {
            "EmbedUrl": embed_url,
            "AnonymousUserArn": user_arn,
        }
        response = client.get(
            reverse("dashboard-detail", args=[dashboard.quicksight_id]),
            data={"email": email},
        )

        assert response.status_code == expected_status

        if expected_status == status.HTTP_200_OK:
            result = response.data
            assert result["embed_url"] == embed_url
            assert result["anonymous_user_arn"] == user_arn
