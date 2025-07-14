# Third-party
from django.urls import path

from . import views

urlpatterns = [
    path("pagerduty/", views.pagerduty_webhook, name="pagerduty"),
]
