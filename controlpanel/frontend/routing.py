from django.urls import path

from controlpanel.frontend.consumers import SSEConsumer


urlpatterns = [
    path('events/', SSEConsumer),
]
