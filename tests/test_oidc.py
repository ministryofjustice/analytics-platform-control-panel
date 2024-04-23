# Standard library
from unittest.mock import Mock

# Third-party
import pytest

# First-party/Local
from controlpanel.oidc import StateMismatchHandler


@pytest.mark.parametrize(
    "email, success_url",
    [
        ("", "/"),
        ("example@justice.gov.uk", "/tools/"),
    ],
)
def test_success_url(users, email, success_url):
    request = Mock()
    request.session.get.return_value = "/tools/"
    user = users["normal_user"]
    user.justice_email = email
    view = StateMismatchHandler()
    view.request = request
    view.user = user
    assert view.success_url == success_url
