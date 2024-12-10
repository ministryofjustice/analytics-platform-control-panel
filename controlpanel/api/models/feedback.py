# Third-party
from django.db import models
from django.utils import timezone


class Feedback(models.Model):
    SATISFACTION_RATINGS = [
        (5, "Very satisfied"),
        (4, "Satisfied"),
        (3, "Neither satisfied or dissatisfied"),
        (2, "Dissatisfied"),
        (1, "Very dissatisfied"),
    ]

    satisfaction_rating = models.IntegerField(
        choices=SATISFACTION_RATINGS,
        null=False,
        blank=False,
    )

    suggestions = models.TextField(blank=True)
    date_added = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "control_panel_api_feedback"
