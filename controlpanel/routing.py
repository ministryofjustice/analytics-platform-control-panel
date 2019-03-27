from channels.routing import ChannelNameRouter, ProtocolTypeRouter, URLRouter

from controlpanel.frontend.consumers import ToolConsumer
from controlpanel.frontend.routing import urlpatterns as frontend_urlpatterns


application = ProtocolTypeRouter({
    'channel': ChannelNameRouter({
        'tools': ToolConsumer,
    }),
    'http': URLRouter(frontend_urlpatterns),
})
