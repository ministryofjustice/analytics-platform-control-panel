# Third-party
from django.db import models
from django_extensions.db.models import TimeStampedModel


class StatusPageEvent(TimeStampedModel):
    POST_TYPE_INCIDENT = "incident"
    POST_TYPE_MAINTENANCE = "maintenance"
    POST_TYPE_CHOICES = [
        (POST_TYPE_INCIDENT, "Incident"),
        (POST_TYPE_MAINTENANCE, "Maintenance"),
    ]
    INCIDENT_COLOUR = "orange"
    MAINTENANCE_COLOUR = "blue"
    SEVERITY_CHOICES = [
        ("info", "Info"),
        ("minor", "Minor"),
        ("major", "Major"),
        ("critical", "Critical"),
    ]
    STATUS_CHOICES = [
        ("investigating", "Investigating"),
        ("detected", "Detected"),
        ("resolved", "Resolved"),
        ("scheduled", "Scheduled"),
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
    ]

    title = models.CharField(max_length=200)
    post_type = models.CharField(max_length=20, choices=POST_TYPE_CHOICES)
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    href = models.URLField(unique=True)
    raw_payload = models.JSONField()

    def __str__(self):
        return f"[{self.post_type.upper()}] {self.title}"

    @property
    def label_colour(self):
        return {
            self.POST_TYPE_MAINTENANCE: self.MAINTENANCE_COLOUR,
            self.POST_TYPE_INCIDENT: self.INCIDENT_COLOUR,
        }.get(self.post_type, self.POST_TYPE_INCIDENT)
