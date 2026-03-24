# Standard library
from unittest.mock import patch

# Third-party
import pytest
from django.urls import reverse
from model_bakery import baker
from rest_framework import status
from rest_framework.test import APIClient

# First-party/Local
from controlpanel.api.jwt_auth import AuthenticatedServiceClient

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
def m2m_client():
    payload = {
        "sub": "abc123@clients",
        "gty": "client-credentials",
        "scope": "list:dashboard retrieve:dashboard",
    }
    user = AuthenticatedServiceClient(jwt_payload=payload)
    client = APIClient()
    client.force_authenticate(user=user)
    return client


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
        },
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
    viewer = baker.make("api.DashboardViewer", email="dashboard.viewer@justice.gov.uk")
    return baker.make(
        "api.DashboardViewerAccess",
        dashboard=dashboard,
        viewer=viewer,
        shared_by=users["dashboard_admin"],
    )


@pytest.fixture
def dashboard_domain(dashboard):
    domain = baker.make("api.DashboardDomain", name="cica.gov.uk")
    return baker.make(
        "api.DashboardDomainAccess",
        dashboard=dashboard,
        domain=domain,
        added_by=dashboard.created_by,
    )


@pytest.mark.parametrize(
    "email, expected_status, expected_count",
    [
        ("dashboard.admin@justice.gov.uk", status.HTTP_200_OK, 1),
        ("dashboard.viewer@justice.gov.uk", status.HTTP_200_OK, 1),
        ("domain.viewer@cica.gov.uk", status.HTTP_200_OK, 1),
        ("no.access@test.gov.uk", status.HTTP_200_OK, 0),
        (None, status.HTTP_400_BAD_REQUEST, 0),
        ("DASHBOARD.ADMIN@JUSTICE.GOV.UK", status.HTTP_200_OK, 1),
        ("Dashboard.Viewer@Justice.Gov.Uk", status.HTTP_200_OK, 1),
        ("DOMAIN.VIEWER@CICA.GOV.UK", status.HTTP_200_OK, 1),
    ],
)
def test_list(
    m2m_client,
    users,
    dashboard,
    dashboard_viewer,
    dashboard_domain,
    email,
    expected_status,
    expected_count,
):
    data = {"email": email} if email else {}
    response = m2m_client.get(reverse("dashboard-list"), data=data)

    assert response.status_code == expected_status

    if expected_status == status.HTTP_200_OK:
        assert response.data["count"] == expected_count

        if expected_count > 0:
            result = response.data["results"][0]
            assert result["quicksight_id"] == dashboard.quicksight_id
            assert result["admins"][0]["email"] == users["dashboard_admin"].justice_email


@pytest.mark.parametrize(
    "email, expected_status",
    [
        ("no.access@test.gov.uk", status.HTTP_404_NOT_FOUND),
        ("", status.HTTP_400_BAD_REQUEST),
    ],
)
def test_retrieve_error(
    m2m_client,
    dashboard,
    email,
    expected_status,
):
    with patch("controlpanel.api.models.dashboard.Dashboard.get_embed_url"):
        response = m2m_client.get(
            reverse("dashboard-detail", args=[dashboard.quicksight_id]),
            data={"email": email},
        )

        assert response.status_code == expected_status


@pytest.mark.parametrize(
    "email, embed_url, user_arn",
    [
        (
            "dashboard.viewer@justice.gov.uk",
            "https://quicksight-embed-url-viewer",
            "some:viewer:arn",
        ),
        (
            "DASHBOARD.VIEWER@JUSTICE.GOV.UK",
            "https://quicksight-embed-url-viewer",
            "some:viewer:arn",
        ),
    ],
)
def test_retrieve_success_shared_as_viewer(
    m2m_client,
    dashboard,
    dashboard_viewer,
    dashboard_domain,
    email,
    embed_url,
    user_arn,
):
    with patch("controlpanel.api.models.dashboard.Dashboard.get_embed_url") as get_embed_url:
        get_embed_url.return_value = {
            "EmbedUrl": embed_url,
            "AnonymousUserArn": user_arn,
        }

        response = m2m_client.get(
            reverse("dashboard-detail", args=[dashboard.quicksight_id]),
            data={"email": email},
        )

        assert response.status_code == status.HTTP_200_OK

        result = response.data
        assert result["embed_url"] == embed_url
        assert result["anonymous_user_arn"] == user_arn
        assert result["shared_by_email"] == dashboard_viewer.shared_by.justice_email
        assert result["shared_by_name"] == dashboard_viewer.shared_by.name
        assert result["shared_on"] == dashboard_viewer.created
        assert result["shared_via_domain"] is False


@pytest.mark.parametrize(
    "email, embed_url, user_arn",
    [
        ("domain.viewer@cica.gov.uk", "https://quicksight-embed-url-domain", "some:domain:arn"),
        ("DOMAIN.VIEWER@CICA.GOV.UK", "https://quicksight-embed-url-domain", "some:domain:arn"),
    ],
)
def test_retrieve_success_shared_as_domain_viewer(
    m2m_client,
    dashboard,
    dashboard_domain,
    email,
    embed_url,
    user_arn,
):
    with patch("controlpanel.api.models.dashboard.Dashboard.get_embed_url") as get_embed_url:
        get_embed_url.return_value = {
            "EmbedUrl": embed_url,
            "AnonymousUserArn": user_arn,
        }

        response = m2m_client.get(
            reverse("dashboard-detail", args=[dashboard.quicksight_id]),
            data={"email": email},
        )

        assert response.status_code == status.HTTP_200_OK

        result = response.data
        assert result["embed_url"] == embed_url
        assert result["anonymous_user_arn"] == user_arn
        assert result["shared_by_email"] == dashboard_domain.added_by.justice_email
        assert result["shared_by_name"] == dashboard_domain.added_by.name
        assert result["shared_on"] == dashboard_domain.created
        assert result["shared_via_domain"] is True


@pytest.mark.parametrize(
    "email, embed_url, user_arn",
    [
        ("dashboard.admin@justice.gov.uk", "https://quicksight-embed-url-viewer", "some:admin:arn"),
        ("Dashboard.Admin@Justice.Gov.Uk", "https://quicksight-embed-url-viewer", "some:admin:arn"),
    ],
)
def test_retrieve_success_as_admin(
    m2m_client,
    dashboard,
    email,
    embed_url,
    user_arn,
):
    with patch("controlpanel.api.models.dashboard.Dashboard.get_embed_url") as get_embed_url:
        get_embed_url.return_value = {
            "EmbedUrl": embed_url,
            "AnonymousUserArn": user_arn,
        }

        response = m2m_client.get(
            reverse("dashboard-detail", args=[dashboard.quicksight_id]),
            data={"email": email},
        )

        assert response.status_code == status.HTTP_200_OK

        result = response.data
        assert result["embed_url"] == embed_url
        assert result["anonymous_user_arn"] == user_arn
        assert result["shared_by_email"] is None
        assert result["shared_by_name"] is None
        assert result["shared_on"] == dashboard.created
        assert result["shared_via_domain"] is False
