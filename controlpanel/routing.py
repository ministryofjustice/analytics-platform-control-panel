from channels.auth import AuthMiddlewareStack
from channels.routing import ChannelNameRouter, ProtocolTypeRouter, URLRouter
from django.urls import re_path
from django.core.asgi import get_asgi_application

from controlpanel.frontend.consumers import BackgroundTaskConsumer, SSEConsumer


application = ProtocolTypeRouter({
    'channel': ChannelNameRouter({
        'background_tasks': BackgroundTaskConsumer.as_asgi(),
    }),
    'http': AuthMiddlewareStack(
        URLRouter([
            re_path(r"^events/$", SSEConsumer.as_asgi()),
            # Default http routing for rest of Django app
            re_path(r"", get_asgi_application()),
        ]),
    )
})
