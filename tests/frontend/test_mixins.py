# Standard library
from unittest import mock

# Third-party
import pytest

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
    mock_event_model.objects.exclude.return_value = mock_qs

    view = DummyStatusPageEventView()
    context = view.get_context_data()

    assert context["pagerduty_posts"] == mock_qs
    assert context["display_service_info"] is True


@mock.patch("controlpanel.frontend.mixins.StatusPageEvent")
def test_mixin_adds_context_without_events(mock_event_model):
    mock_qs = mock.Mock()
    mock_qs.exists.return_value = False
    mock_event_model.objects.exclude.return_value = mock_qs

    view = DummyStatusPageEventView()
    context = view.get_context_data()

    assert context["pagerduty_posts"] == mock_qs
    assert context["display_service_info"] is False
