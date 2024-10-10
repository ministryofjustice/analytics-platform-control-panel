# Third-party
import pytest
from django.utils import timezone

# First-party/Local
from controlpanel.api.models.task import Task


def four_days_ago():
    return timezone.now() - timezone.timedelta(days=4)


@pytest.mark.parametrize(
    "task, expected_status",
    [
        (Task(cancelled=True), "CANCELLED"),
        (Task(completed=True), "COMPLETED"),
        (
            Task(
                completed=False,
                cancelled=False,
                created=four_days_ago(),
            ),
            "FAILED",
        ),
        (
            Task(
                completed=False,
                cancelled=False,
                created=four_days_ago() + timezone.timedelta(hours=1),
            ),
            "PENDING",
        ),
        (
            Task(
                completed=False, cancelled=False, created=four_days_ago(), retried_at=timezone.now()
            ),
            "RETRYING",
        ),
        (
            Task(
                completed=False,
                cancelled=False,
                created=four_days_ago() - timezone.timedelta(hours=1),
                retried_at=four_days_ago() - timezone.timedelta(hours=1),
            ),
            "FAILED",
        ),
    ],
    ids=["cancelled", "completed", "failed", "pending", "retrying", "retry_failed"],
)
def test_status(task, expected_status):
    assert task.status == expected_status
