# Standard library
from unittest.mock import MagicMock, patch

# Third-party
import pytest
from django.conf import settings
from django.urls import reverse

# First-party/Local
from controlpanel.api.exceptions import DeleteViewerError
from controlpanel.api.models.dashboard import Dashboard, DashboardViewer


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


@patch("controlpanel.api.models.dashboard.Dashboard.viewer_access")
def test_remove_viewers(mock_viewer_access, govuk_notify_send_email):
    """
    Test the remove_viewers method of the Dashboard model.
    """
    dashboard = Dashboard(name="Test Dashboard")
    viewer = DashboardViewer(email="foo@example.com")
    admin = MagicMock()
    admin.justice_email = "admin@example.com"

    mock_access = MagicMock()
    mock_viewer_access.get.return_value = mock_access

    dashboard.delete_viewers([viewer], admin=admin)

    mock_viewer_access.get.assert_called_once_with(viewer=viewer)
    mock_access.delete.assert_called_once()
    govuk_notify_send_email.assert_called_once_with(
        email_address="foo@example.com",
        template_id=settings.NOTIFY_DASHBOARD_REVOKED_TEMPLATE_ID,
        personalisation={
            "dashboard": dashboard.name,
            "dashboard_link": dashboard.url,
            "dashboard_home": settings.DASHBOARD_SERVICE_URL,
            "revoked_by": admin.justice_email,
        },
    )
