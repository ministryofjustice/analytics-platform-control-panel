from django.conf import settings
import slack


CREATE_SUPERUSER_MESSAGE = "`{username}` was created as a superuser"
GRANT_SUPERUSER_ACCESS_MESSAGE = "`{username}` was granted superuser status"


def notify_team(message, request_user=None):
    token = settings.SLACK['api_token']
    if token:
        if request_user:
            message = f"{message} by `{request_user.username}`"
        slack.WebClient(token=token).chat_postMessage(
            as_user=False,
            username=f"Control Panel [{settings.ENV}]",
            channel=settings.SLACK["channel"],
            text=message,
        )

