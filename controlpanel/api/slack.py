from django.conf import settings
import slack


if settings.SLACK['api_token'] is None:
    raise ValueError("SLACK_API_TOKEN environment variable is required")


CREATE_SUPERUSER_MESSAGE = "`{username}` was created as a superuser"
GRANT_SUPERUSER_ACCESS_MESSAGE = "`{username}` was granted superuser status"


def notify_team(message, request_username=None):
    if request_username:
        message = f"{message} by `{request_username}`"
    slack.WebClient(token=settings.SLACK['api_token']).chat_postMessage(
        as_user=False,
        username=f"Control Panel [{settings.ENV}]",
        channel=settings.SLACK["channel"],
        text=message,
    )
