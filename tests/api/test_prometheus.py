# Third-party
import pytest
from prometheus_client import REGISTRY

# First-party/Local
from controlpanel.api.models import User


def _get_counter_value(name):
    _metrics = [m for m in REGISTRY.collect() if m.name == name]
    counter = _metrics[0]
    sample = counter.samples[0]
    return sample.value


@pytest.mark.django_db
def test_login_counters(client):
    """Ensure that custom metrics set on user is being triggered"""
    user = User.objects.create(username="test-user")
    client.force_login(user)
    before = _get_counter_value("django_control_panel_login_events")
    client.force_login(user)
    after = _get_counter_value("django_control_panel_login_events")
    assert 1 == (after - before)
