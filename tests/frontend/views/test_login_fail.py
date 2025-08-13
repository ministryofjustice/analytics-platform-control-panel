# Third-party
import pytest

# First-party/Local
from controlpanel.frontend.views.login_fail import LoginFail


@pytest.mark.parametrize(
    "error, should_show_prompt",
    [(LoginFail.ERROR_USE_GITHUB, True), ("Access denied", False), ("", False), (None, False)],
)
def test_login_fail_show_github_error(rf, error, should_show_prompt):
    query_params = {"error": error}
    if not error:
        query_params = {}
    request = rf.get("/", query_params=query_params)
    view = LoginFail()
    view.request = request

    context = view.get_context_data()

    assert context["show_github_login_prompt"] is should_show_prompt
