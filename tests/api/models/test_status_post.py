# Standard library
from datetime import datetime
from zoneinfo import ZoneInfo

# Third-party
import pytest
from django.utils.timezone import make_aware

# First-party/Local
from controlpanel.api.models import StatusPageEvent


@pytest.mark.parametrize(
    "field_name",
    [
        "reported_at_local",
        "starts_at_local",
        "ends_at_local",
    ],
)
def test_time_property_formats_correctly_bst(field_name):
    dt_utc = make_aware(datetime(2025, 7, 20, 12, 0))

    event = StatusPageEvent(
        reported_at=dt_utc,
        starts_at=dt_utc,
        ends_at=dt_utc,
    )

    value = getattr(event, field_name)
    assert value == "20 Jul 2025, 13:00"


@pytest.mark.parametrize(
    "field_name",
    [
        "reported_at_local",
        "starts_at_local",
        "ends_at_local",
    ],
)
def test_time_property_formats_correctly_gmt(field_name):
    dt_utc = make_aware(datetime(2025, 1, 1, 12, 0))
    event = StatusPageEvent(reported_at=dt_utc, starts_at=dt_utc, ends_at=dt_utc)
    result = getattr(event, field_name)
    assert result == "1 Jan 2025, 12:00"
