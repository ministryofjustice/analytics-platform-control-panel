from unittest.mock import patch

import pytest

from controlpanel.api import slack


@pytest.fixture
def message_sent(settings, slack_WebClient):
    def check_sent(message):
        slack_WebClient.assert_called_with(token=settings.SLACK["api_token"])
        slack_WebClient.return_value.chat_postMessage.assert_called_with(
            channel=settings.SLACK["channel"],
            text=f"{message} [{settings.ENV}]",
        )
        return True
    return check_sent


def test_send_notification(message_sent):
    message = "test message"
    slack.send_notification(message)

    assert message_sent(message)

@pytest.mark.parametrize(
    "request_user",
    [
        None,
        "normal_user",
    ],
    ids=[
        "no-request-user",
        "with-request-user",
    ]
)
def test_notify_superuser_created(message_sent, users, request_user):
    user = users['other_user']
    expected_message = slack.CREATE_SUPERUSER_MESSAGE.format(username=user.username)
    by_username = None
    if request_user:
        by_username = users[request_user].username
        expected_message = f"{expected_message} by `{by_username}`"
    slack.notify_superuser_created(user.username, by_username=by_username)

    assert message_sent(expected_message)
