# Standard library
from unittest.mock import MagicMock, patch

# Third-party
import pytest
from django.conf import settings

# First-party/Local
from controlpanel.api.models.dashboard import Dashboard, DashboardViewer, DeleteCustomerError


@patch("controlpanel.api.models.dashboard.Dashboard.viewers")
def test_remove_viewers(mock_viewers, govuk_notify_send_email):
    """
    Test the remove_viewers method of the Dashboard model.
    """
    dashboard = Dashboard(name="Test Dashboard")
    viewer = DashboardViewer(email="foo@example.com")
    dashboard.delete_viewers([viewer])

    mock_viewers.remove.assert_called_once_with(viewer)
    govuk_notify_send_email.assert_called_once_with(
        email_address="foo@example.com",
        template_id=settings.NOTIFY_DASHBOARD_REVOKED_TEMPLATE_ID,
        personalisation={
            "dashboard": dashboard.name,
            "dashboard_link": dashboard.url,
            "dashboard_home": settings.DASHBOARD_SERVICE_URL,
        },
    )


@pytest.mark.parametrize(
    "ids, return_value, success",
    [
        ([1, 2, 3], [MagicMock(), MagicMock(), MagicMock()], True),
        ([4, 5, 6], None, False),
    ],
)
@patch("controlpanel.api.models.dashboard.DashboardViewer.objects.filter")
@patch("controlpanel.api.models.dashboard.Dashboard.delete_viewers")
def test_delete_customers_by_id(mock_delete_viewers, mock_filter, ids, return_value, success):
    """
    Test the delete_customers_by_id method of the Dashboard model.
    """
    dashboard = Dashboard(name="Test Dashboard")
    mock_filter.return_value = return_value

    if success:
        dashboard.delete_customers_by_id(ids)
        mock_delete_viewers.assert_called_once_with(return_value)
    else:
        with pytest.raises(DeleteCustomerError):
            dashboard.delete_customers_by_id(ids)
            mock_delete_viewers.assert_not_called()


@pytest.mark.parametrize(
    "email, return_value, success",
    [
        ("found@example.com", [MagicMock()], True),
        ("not-found@example.com", None, False),
    ],
)
@patch("controlpanel.api.models.dashboard.DashboardViewer.objects.filter")
@patch("controlpanel.api.models.dashboard.Dashboard.delete_viewers")
def test_delete_customers_by_email(mock_delete_viewers, mock_filter, email, return_value, success):
    """
    Test the delete_customers_by_id method of the Dashboard model.
    """
    dashboard = Dashboard(name="Test Dashboard")
    mock_filter.return_value = return_value

    if success:
        dashboard.delete_customers_by_id(email)
        mock_delete_viewers.assert_called_once_with(return_value)
    else:
        with pytest.raises(DeleteCustomerError):
            dashboard.delete_customers_by_id(email)
            mock_delete_viewers.assert_not_called()
