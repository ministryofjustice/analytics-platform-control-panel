# Third-party
import pytest
from django.conf import settings

# First-party/Local
from controlpanel.frontend.views.login_fail import LoginFail


class TestLoginFailView:
    """Test suite for the LoginFail view."""

    @pytest.mark.parametrize(
        "error, should_show_prompt",
        [
            (LoginFail.ERROR_USE_GITHUB, True),
            ("Access denied", False),
            ("session_expired", False),
            ("invalid_state", False),
            ("", False),
            (None, False),
        ],
    )
    def test_show_github_login_prompt_logic(self, rf, error, should_show_prompt):
        """Test that GitHub login prompt is only shown for the specific GitHub error."""
        query_params = {"error": error} if error is not None else {}
        request = rf.get("/", query_params=query_params)
        view = LoginFail()
        view.request = request

        context = view.get_context_data()

        assert context["show_github_login_prompt"] is should_show_prompt

    def test_context_data_values(self, rf):
        """Test that context variables have correct values from settings."""
        request = rf.get("/")
        view = LoginFail()
        view.request = request

        context = view.get_context_data()

        # Test the application-specific logic
        assert context["environment"] == settings.ENV
        assert context["auth0_logout_url"] == settings.AUTH0["logout_url"]
        assert context["show_github_login_prompt"] is False  # No error param

    def test_context_data_with_github_error(self, rf):
        """Test context data when GitHub error is present."""
        request = rf.get("/", query_params={"error": LoginFail.ERROR_USE_GITHUB})
        view = LoginFail()
        view.request = request

        context = view.get_context_data()

        assert context["show_github_login_prompt"] is True
        # Verify other context remains correct
        assert context["environment"] == settings.ENV
        assert context["auth0_logout_url"] == settings.AUTH0["logout_url"]

    @pytest.mark.parametrize(
        "error_value, expected_show_prompt",
        [
            ("use_github", True),  # Exact match
            ("USE_GITHUB", False),  # Case sensitivity
            ("use_github_auth", False),  # Partial match
            (" use_github ", False),  # Whitespace
        ],
    )
    def test_github_error_exact_match_required(self, rf, error_value, expected_show_prompt):
        """Test that GitHub error detection requires exact string match."""
        request = rf.get("/", query_params={"error": error_value})
        view = LoginFail()
        view.request = request

        context = view.get_context_data()

        assert context["show_github_login_prompt"] is expected_show_prompt
