from channels.auth import AuthMiddlewareStack
from channels.http import AsgiHandler
from channels.routing import ChannelNameRouter, ProtocolTypeRouter, URLRouter
from django.conf.urls import url
from django.urls import path

from controlpanel.frontend.consumers import BackgroundTaskConsumer, SSEConsumer


application = ProtocolTypeRouter({
    'channel': ChannelNameRouter({
        'background_tasks': BackgroundTaskConsumer,
    }),
    'http': AuthMiddlewareStack(
        URLRouter([
            url(r"^events/$", SSEConsumer),
            # Default http routing for rest of Django app
            url(r"", AsgiHandler),
        ]),
    )
})
