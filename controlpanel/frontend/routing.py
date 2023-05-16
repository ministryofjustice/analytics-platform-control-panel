# Third-party
from django.urls import path

# First-party/Local
from controlpanel.frontend.consumers import SSEConsumer

urlpatterns = [
    path("events/", SSEConsumer),
]
