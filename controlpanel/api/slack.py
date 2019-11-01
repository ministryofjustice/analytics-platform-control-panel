from django.conf import settings
from slack import WebClient


def notify_team(msg):
    WebClient(token=settings.SLACK["api_token"]).chat_postMessage(
        as_user=False,
        username=f"Control Panel [{settings.ENV}]",
        channel=settings.SLACK["channel"],
        text=msg,
    )

