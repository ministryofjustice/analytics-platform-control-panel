# Standard library
from unittest import mock

# First-party/Local
from controlpanel.frontend.views import release


def test_release_detail_context_data():
    """
    Ensure the context data for the release detail view contains the expected
    list of beta users (if they exist).
    """
    v = release.ReleaseDetail()
    v.request = mock.MagicMock()
    v.request.method = "GET"
    mock_object = mock.MagicMock()
    mock_user1 = mock.MagicMock()
    mock_user2 = mock.MagicMock()
    mock_user1.username = "aldo"
    mock_user2.username = "nicholas"
    mock_object.target_users.all.return_value = [mock_user1, mock_user2]
    v.object = mock_object
    result = v.get_context_data()
    assert result["target_users"] == "aldo, nicholas"
