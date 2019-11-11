from unittest.mock import patch

import pytest

from controlpanel.api import slack


def test_slack_send_notification(settings, slack_WebClient):
    slack.send_notification("test message")
    slack_WebClient.assert_called_with(token=settings.SLACK["api_token"])
    slack_WebClient.return_value.chat_postMessage.assert_called_with(
        as_user=False,
        username=f"Control Panel [{settings.ENV}]",
        channel=settings.SLACK["channel"],
        text="test message",
    )


@pytest.mark.parametrize(
    "message, request_user",
    [
        ("test", None),
        ("test", "normal_user"),
    ],
    ids=[
        "no-request-user",
        "with-request-user",
    ]
)
def test_slack_notify_superuser_created(
    settings,
    slack_WebClient,
    users,
    message,
    request_user,
):
    user = users['other_user']
    expected_message = slack.CREATE_SUPERUSER_MESSAGE.format(username=user.username)
    by_username = None
    if request_user:
        by_username = users[request_user].username
        expected_message = f"{expected_message} by `{by_username}`"
    slack.notify_superuser_created(user.username, by_username=by_username)

    slack_WebClient.assert_called_with(token=settings.SLACK["api_token"])
    slack_WebClient.return_value.chat_postMessage.assert_called_with(
        as_user=False,
        username=f"Control Panel [{settings.ENV}]",
        channel=settings.SLACK["channel"],
        text=expected_message,
    )
