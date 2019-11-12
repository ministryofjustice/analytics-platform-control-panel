from django.conf import settings
import slack


if settings.SLACK['api_token'] is None:
    raise ValueError("SLACK_API_TOKEN environment variable is required")


CREATE_SUPERUSER_MESSAGE = "`{username}` was granted superuser access"


def notify_superuser_created(username, by_username=None):
    message = CREATE_SUPERUSER_MESSAGE.format(username=username)
    if by_username:
        message = f"{message} by `{by_username}`"
    send_notification(message)


def send_notification(message):
    slack.WebClient(token=settings.SLACK['api_token']).chat_postMessage(
        as_user=False,
        username=f"Control Panel [{settings.ENV}]",
        channel=settings.SLACK["channel"],
        text=message,
    )
