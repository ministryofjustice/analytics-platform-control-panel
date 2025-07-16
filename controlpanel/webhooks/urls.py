# Third-party
from django.urls import path

from . import views

app_name = "webhooks"

urlpatterns = [
    path("pagerduty/", views.PagerDutyWebhookView.as_view(), name="pagerduty"),
]
