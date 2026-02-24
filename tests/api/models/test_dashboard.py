# Standard library
from unittest.mock import patch

# Third-party
import pytest
from django.conf import settings
from django.urls import reverse
from model_bakery import baker

# First-party/Local
from controlpanel.api.models.dashboard import Dashboard, DashboardAdminAccess, DashboardViewerAccess


class TestDashboardUrls:
    """Tests for Dashboard URL helper methods."""

    def test_get_absolute_url_default(self):
        dashboard = Dashboard(pk=42)
        expected = reverse("manage-dashboard-sharing", kwargs={"pk": 42})
        assert dashboard.get_absolute_url() == expected

    def test_get_absolute_url_custom_viewname(self):
        dashboard = Dashboard(pk=42)
        expected = reverse("delete-dashboard", kwargs={"pk": 42})
        assert dashboard.get_absolute_url(viewname="delete-dashboard") == expected

    def test_get_absolute_add_viewers_url(self):
        dashboard = Dashboard(pk=42)
        expected = reverse("add-dashboard-viewers", kwargs={"pk": 42})
        assert dashboard.get_absolute_add_viewers_url() == expected

    def test_get_absolute_add_admins_url(self):
        dashboard = Dashboard(pk=42)
        expected = reverse("add-dashboard-admin", kwargs={"pk": 42})
        assert dashboard.get_absolute_add_admins_url() == expected

    def test_get_absolute_grant_domain_url(self):
        dashboard = Dashboard(pk=42)
        expected = reverse("grant-domain-access", kwargs={"pk": 42})
        assert dashboard.get_absolute_grant_domain_url() == expected


@pytest.fixture
def dashboard(users):
    return baker.make("api.Dashboard", created_by=users["superuser"])


@pytest.fixture
@patch("controlpanel.api.models.dashboard_viewer.DashboardViewer.add_viewer")
def viewer_with_access(mock_add_viewer, dashboard, users):
    viewer = baker.make("api.DashboardViewer", email="viewer@example.com")
    access = baker.make(
        "api.DashboardViewerAccess",
        dashboard=dashboard,
        viewer=viewer,
        shared_by=users["superuser"],
    )
    return viewer, access


@pytest.mark.django_db
def test_delete_viewers(users, dashboard, viewer_with_access, govuk_notify_send_email):
    viewer, access = viewer_with_access
    access_id = access.id
    admin = users["superuser"]

    dashboard.delete_viewers([viewer], admin=admin)

    assert not DashboardViewerAccess.objects.filter(id=access_id).exists()
    HistoricalDashboardViewerAccess = DashboardViewerAccess.history.model
    history_record = HistoricalDashboardViewerAccess.objects.filter(
        id=access_id,
        history_type="-",
    ).first()
    assert history_record is not None, (
        "No deletion history record found. "
        "Ensure delete_viewers uses .get().delete() instead of .remove()"
    )
    assert history_record.dashboard_id == dashboard.id
    assert history_record.viewer_id == viewer.id

    govuk_notify_send_email.assert_called_once_with(
        email_address="viewer@example.com",
        template_id=settings.NOTIFY_DASHBOARD_REVOKED_TEMPLATE_ID,
        personalisation={
            "dashboard": dashboard.name,
            "dashboard_link": dashboard.url,
            "dashboard_home": settings.DASHBOARD_SERVICE_URL,
            "revoked_by": admin.justice_email,
        },
    )


@pytest.fixture
def admin_with_access(dashboard, users):
    access = baker.make(
        "api.DashboardAdminAccess",
        dashboard=dashboard,
        user=users["normal_user"],
        added_by=users["superuser"],
    )
    return users["normal_user"], access


@pytest.mark.django_db
def test_delete_admin(users, dashboard, admin_with_access, govuk_notify_send_email):
    admin_user, access = admin_with_access
    access_id = access.id
    requesting_admin = users["superuser"]

    dashboard.delete_admin(user=admin_user, admin=requesting_admin)

    assert not DashboardAdminAccess.objects.filter(id=access_id).exists()

    HistoricalDashboardAdminAccess = DashboardAdminAccess.history.model
    history_record = HistoricalDashboardAdminAccess.objects.filter(
        id=access_id,
        history_type="-",
    ).first()
    assert history_record is not None, (
        "No deletion history record found. "
        "Ensure delete_admin uses .get().delete() instead of .remove()"
    )
    assert history_record.dashboard_id == dashboard.id
    assert history_record.user_id == admin_user.id
    govuk_notify_send_email.assert_called_once_with(
        email_address=admin_user.justice_email,
        template_id=settings.NOTIFY_DASHBOARD_ADMIN_REMOVED_TEMPLATE_ID,
        personalisation={
            "dashboard": dashboard.name,
            "revoked_by": requesting_admin.justice_email,
        },
    )
