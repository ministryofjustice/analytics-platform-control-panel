# Standard library
from unittest.mock import Mock, patch

# Third-party
import pytest
from django.conf import settings

# First-party/Local
from controlpanel.oidc import OIDCSubAuthenticationBackend, StateMismatchHandler


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


@pytest.mark.django_db
@pytest.mark.parametrize(
    "email, name, expected_name, expected_justice_email",
    [
        ("email@example.com", "User, Test", "Test User", None),
        ("email@example.com", "Test User", "Test User", None),
        ("email@justice.gov.uk", "User, Test", "Test User", "email@justice.gov.uk"),
        ("email@justice.gov.uk", "Test User", "Test User", "email@justice.gov.uk"),
        ("email@cica.gov.uk", "Test User", "Test User", "email@cica.gov.uk"),
        ("email@CICA.GOV.UK", "Test User", "Test User", "email@CICA.GOV.UK"),
    ],
)
def test_create_user(email, name, expected_name, expected_justice_email):
    with patch("controlpanel.api.cluster.User.create"):
        user = OIDCSubAuthenticationBackend().create_user(
            {
                "sub": "123",
                settings.OIDC_FIELD_USERNAME: "testuser",
                settings.OIDC_FIELD_EMAIL: email,
                settings.OIDC_FIELD_NAME: name,
            }
        )
        assert user.name == expected_name
        assert user.justice_email == expected_justice_email


@pytest.mark.parametrize(
    "email, expected",
    [
        ("email@example.com", None),
        ("email@justice.gov.uk", "email@justice.gov.uk"),
        ("email@JUSTICE.GOV.UK", "email@JUSTICE.GOV.UK"),
        ("email@cica.gov.uk", "email@cica.gov.uk"),
        ("email@CICA.GOV.UK", "email@CICA.GOV.UK"),
    ],
)
def test_get_justice_email(email, expected):
    assert OIDCSubAuthenticationBackend().get_justice_email(email) == expected
