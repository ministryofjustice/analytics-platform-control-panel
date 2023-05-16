# Standard library
from unittest.mock import Mock, patch

# Third-party
import pytest
from rest_framework.reverse import reverse

# First-party/Local
from tests.frontend.views.test_app import github_api_token, users  # noqa: F811

BASIC_GOOD_DATA = [
    dict(html_url="http://example.com", full_name="my-repo"),
    dict(html_url="http://example.com", full_name="my-repo2"),
    dict(html_url="http://example.com", full_name="my-repo3"),
]
ARCHIVED_GOOD = [dict(**i, archived=False) for i in BASIC_GOOD_DATA]
FILTERED_ARCHIVED_GOOD = [i.copy() for i in ARCHIVED_GOOD]
FILTERED_ARCHIVED_GOOD[2]["archived"] = True
BAD_JSON = dict(data="should expect an array")
NULL_KEY_ENTRY = [dict(unknow_key="here", full_name="my-repo")]


@pytest.mark.parametrize(
    "input,expected_status,expected_result",
    [
        (dict(status_code=200, json=lambda: []), 200, []),
        (dict(status_code=404, json=lambda: []), 200, []),
        (dict(status_code=200, json=lambda: ARCHIVED_GOOD), 200, BASIC_GOOD_DATA),
        (
            dict(status_code=200, json=lambda: FILTERED_ARCHIVED_GOOD),
            200,
            BASIC_GOOD_DATA[:2],
        ),
        (dict(status_code=200, json=lambda: BAD_JSON), 200, []),
        (dict(status_code=200, json=lambda: NULL_KEY_ENTRY), 400, []),
    ],
)
def test_github_repo_get(
    client,
    users,  # noqa: F811
    github_api_token,  # noqa: F811
    input,
    expected_status,
    expected_result,
):
    client.force_login(users["app_admin"])

    with patch("controlpanel.api.github.requests.get") as request_fixture:
        request_fixture.return_value = Mock(**input)
        response = client.get(reverse("github-repos", ("testing_github_org",)))
        assert response.status_code == expected_status
        if response.status_code != 400:
            assert response.data == expected_result
