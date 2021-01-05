from unittest import mock
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


def test_release_create_form_valid():
    """
    Ensure that JSON values from a previous release are annotated to the
    new release.

    HERE BE DRAGONS: use of mocking to avoid database related errors with
    pytest test-runner (that doesn't create temp test databases).
    """
    JSONValues = {"foo": "bar", }  # placeholder mock data for JSON values.
    v = release.ReleaseCreate()
    v.request = mock.MagicMock()
    old_tool = mock.MagicMock()
    old_tool.values = JSONValues
    v.request.method = "POST"
    mock_form = mock.MagicMock()
    mock_object = mock.MagicMock()
    mock_form.save.return_value = mock_object
    mock_form.get_target_users.return_value = []
    mock_tool = mock.MagicMock()
    mock_tool.objects.filter().exclude().order_by().first.return_value = old_tool
    with mock.patch("controlpanel.frontend.views.release.Tool", mock_tool):
        v.form_valid(mock_form)
    assert mock_object.values == JSONValues
    mock_object.save.assert_called_once_with()
