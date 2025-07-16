# Standard library
import json
from unittest import mock

# Third-party
import pytest
from django.conf import settings
from django.urls import reverse

# First-party/Local
from controlpanel.webhooks.views import PagerDutyWebhookView


@pytest.fixture
def valid_payload():
    return {
        "title": "AP is down",
        "post_type": "incident",
        "severity": "major",
        "starts_at": "2023-05-15T20:47:12Z",
        "ends_at": None,
        "href": "https://test.example.pagerduty.com/incident_details/PXXXXXX",
    }


@pytest.fixture
def webhook_url():
    return reverse("webhooks:pagerduty") + f"?token={settings.PAGERDUTY_WEBHOOK_SECRET}"


@mock.patch("controlpanel.webhooks.views.StatusPageEvent.objects.update_or_create")
def test_valid_webhook_creates_event(mock_update_or_create, rf, valid_payload, webhook_url):
    mock_event = mock.Mock()
    mock_update_or_create.return_value = (mock_event, True)

    request = rf.post(webhook_url, json.dumps(valid_payload), content_type="application/json")
    response = PagerDutyWebhookView.as_view()(request)

    assert response.status_code == 200
    assert json.loads(response.content)["action"] == "Created"
    mock_update_or_create.assert_called_once()
    assert mock_update_or_create.call_args[1]["href"] == valid_payload["href"]


def test_invalid_token_returns_403(rf, valid_payload):
    url = reverse("webhooks:pagerduty") + "?token=wrong"
    request = rf.post(url, json.dumps(valid_payload), content_type="application/json")
    response = PagerDutyWebhookView.as_view()(request)

    assert response.status_code == 403


def test_invalid_json_returns_400(rf, webhook_url):
    request = rf.post(webhook_url, data="not-json", content_type="application/json")
    response = PagerDutyWebhookView.as_view()(request)

    assert response.status_code == 400


def test_missing_href_returns_400(rf, webhook_url, valid_payload):
    payload = valid_payload.copy()
    del payload["href"]

    request = rf.post(webhook_url, json.dumps(payload), content_type="application/json")
    response = PagerDutyWebhookView.as_view()(request)

    assert response.status_code == 400
