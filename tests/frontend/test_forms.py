import pytest
from unittest import mock
from controlpanel.frontend import forms



def test_tool_release_form_get_target_users():
    """
    Given a string list of comma separated usernames, the expected query to
    return the associated User objects is created.
    """
    f = forms.ToolReleaseForm()
    f.data = {
        "target_users_list": "aldo, nicholas, cal",
    }
    mock_user = mock.MagicMock()
    with mock.patch("controlpanel.frontend.forms.User", mock_user):
        f.get_target_users()
        mock_user.objects.filter.assert_called_once_with(username__in=set([
            "aldo", "nicholas", "cal"
        ]))
