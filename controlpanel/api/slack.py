from django.conf import settings
from slack import WebClient


def notify_team(msg):
    token = settings.SLACK.get('api_token')
    if token:
        WebClient(token=token).chat_postMessage(
            as_user=False,
            username=f"Control Panel [{settings.ENV}]",
            channel=settings.SLACK["channel"],
            text=msg,
        )

