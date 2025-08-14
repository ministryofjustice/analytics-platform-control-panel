# Standard library
from unittest.mock import Mock, patch

# Third-party
import pytest
from django.conf import settings
from django.core.exceptions import SuspiciousOperation
from mozilla_django_oidc.views import OIDCAuthenticationCallbackView

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
        ("email@publicguardian.gov.uk", "Test User", "Test User", "email@publicguardian.gov.uk"),
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


@pytest.mark.django_db
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


@pytest.mark.parametrize(
    "error_description, expected_encoded",
    [
        ("use_github", "use_github"),
        ("access_denied", "access_denied"),
        ("session_expired", "session_expired"),
        ("error with spaces", "error+with+spaces"),
        ("error&with=special&chars", "error%26with%3Dspecial%26chars"),
        ("", ""),
    ],
)
def test_failure_url(rf, error_description, expected_encoded):
    """
    Test that failure_url properly formats and encodes the login failure URL with error parameter.
    """
    request = rf.get("/", query_params={"error_description": error_description})
    view = StateMismatchHandler()
    view.request = request
    assert view.failure_url == f"/login-fail/?error={expected_encoded}"


@pytest.mark.parametrize(
    "query_params, expected_error",
    [
        ({"error_description": "invalid_state"}, "invalid_state"),
        ({"other_param": "value"}, ""),  # No error_description param
        ({}, ""),  # No query params
    ],
)
def test_failure_url_edge_cases(rf, query_params, expected_error):
    """Test failure_url property handles edge cases correctly."""
    request = rf.get("/", query_params=query_params)
    view = StateMismatchHandler()
    view.request = request
    expected_url = f"{settings.LOGIN_REDIRECT_URL_FAILURE}?error={expected_error}"
    assert view.failure_url == expected_url


@pytest.mark.parametrize(
    "exception_message",
    [
        "State mismatch detected",
        "Invalid state parameter",
        "CSRF verification failed",
    ],
)
@patch("controlpanel.oidc.log")
def test_state_mismatch_handler_exception_handling(mock_log, rf, exception_message):
    """Test that StateMismatchHandler properly handles SuspiciousOperation exceptions."""
    request = rf.get("/callback/")
    view = StateMismatchHandler()
    view.request = request

    with patch.object(OIDCAuthenticationCallbackView, "get") as mock_super_get:
        mock_super_get.side_effect = SuspiciousOperation(exception_message)

        response = view.get(request)

        # Verify logging
        mock_log.warning.assert_called_once_with(
            f"Caught {exception_message}: redirecting to login"
        )

        # Verify redirect
        assert response.status_code == 302
        assert response.url == settings.LOGIN_REDIRECT_URL_FAILURE


def test_state_mismatch_handler_successful_flow(rf):
    """Test that StateMismatchHandler passes through successful authentication."""
    request = rf.get("/callback/")
    view = StateMismatchHandler()
    view.request = request

    mock_response = Mock()
    mock_response.status_code = 302
    mock_response.url = "/tools/"

    with patch.object(OIDCAuthenticationCallbackView, "get", return_value=mock_response):
        response = view.get(request)

        assert response == mock_response
