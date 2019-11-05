from unittest.mock import patch

import pytest

from controlpanel.api.slack import notify_team


@pytest.mark.parametrize(
    "message, request_user, expected_message",
    [
        ("test", None, "test"),
        ("test", "normal_user", "test by `bob`"),
    ],
    ids=[
        "no-request-user",
        "with-request-user",
    ]
)
def test_slack_notify_team(
    settings,
    slack_WebClient,
    users,
    message,
    request_user,
    expected_message,
):
    if request_user:
        request_user = users[request_user]
    notify_team(message, request_user)

    slack_WebClient.assert_called_with(token=settings.SLACK["api_token"])
    slack_WebClient.return_value.chat_postMessage.assert_called_with(
        as_user=False,
        username=f"Control Panel [{settings.ENV}]",
        channel=settings.SLACK["channel"],
        text=expected_message,
    )
