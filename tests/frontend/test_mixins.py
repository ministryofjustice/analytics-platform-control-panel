# Standard library
from unittest import mock

# Third-party
import pytest
from django.utils import timezone

# First-party/Local
from controlpanel.frontend.mixins import StatusPageEventMixin


class BaseStubView:
    def get_context_data(self, **kwargs):
        return {}


class DummyStatusPageEventView(StatusPageEventMixin, BaseStubView):
    pass


@mock.patch("controlpanel.frontend.mixins.StatusPageEvent")
def test_mixin_adds_context_with_events(mock_event_model):
    mock_qs = mock.Mock()
    mock_qs.exists.return_value = True
    mock_qs.order_by.return_value.last.return_value.modified = timezone.now()
    mock_event_model.objects.exclude.return_value = mock_qs

    view = DummyStatusPageEventView()
    context = view.get_context_data()

    assert context["pagerduty_posts"] == mock_qs
    assert context["display_service_info"] is True
    assert context["show_pagerduty_posts"] is True


@mock.patch("controlpanel.frontend.mixins.StatusPageEvent")
def test_mixin_adds_context_with_events_dont_show_posts(mock_event_model):
    mock_qs = mock.Mock()
    mock_qs.exists.return_value = True
    mock_qs.order_by.return_value.last.return_value.modified = timezone.now() - timezone.timedelta(
        days=2
    )
    mock_event_model.objects.exclude.return_value = mock_qs

    view = DummyStatusPageEventView()
    context = view.get_context_data()

    assert context["pagerduty_posts"] == mock_qs
    assert context["display_service_info"] is True
    assert context["show_pagerduty_posts"] is False


@mock.patch("controlpanel.frontend.mixins.StatusPageEvent")
def test_mixin_adds_context_without_events(mock_event_model):
    mock_qs = mock.Mock()
    mock_qs.exists.return_value = False
    mock_event_model.objects.exclude.return_value = mock_qs

    view = DummyStatusPageEventView()
    context = view.get_context_data()

    assert "pagerduty_posts" not in context
    assert context["display_service_info"] is False
