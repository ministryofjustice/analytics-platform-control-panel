# Third-party
from django.db import models
from django_extensions.db.models import TimeStampedModel

# First-party/Local
from controlpanel.utils import format_uk_time


class StatusPageEvent(TimeStampedModel):
    POST_TYPE_INCIDENT = "incident"
    POST_TYPE_MAINTENANCE = "maintenance"
    POST_TYPE_CHOICES = [
        (POST_TYPE_INCIDENT, "Incident"),
        (POST_TYPE_MAINTENANCE, "Maintenance"),
    ]
    INCIDENT_COLOUR = "orange"
    MAINTENANCE_COLOUR = "blue"

    SEVERITY_MINOR = "minor"
    SEVERITY_MAJOR = "major"
    SEVERITY_ALL_GOOD = "all good"
    SEVERITY_MAINTENANCE = "maintenance"
    SEVERITY_CHOICES = [
        (SEVERITY_MINOR, "Minor"),
        (SEVERITY_MAJOR, "Major"),
        (SEVERITY_ALL_GOOD, "All good"),
        (SEVERITY_MAINTENANCE, "Maintenance"),
    ]

    STATUS_INVESTIGATING = "investigating"
    STATUS_DETECTED = "detected"
    STATUS_RESOLVED = "resolved"
    STATUS_SCHEDULED = "scheduled"
    STATUS_IN_PROGRESS = "in progress"
    STATUS_COMPLETED = "completed"
    STATUS_CHOICES = [
        (STATUS_INVESTIGATING, "Investigating"),
        (STATUS_DETECTED, "Detected"),
        (STATUS_RESOLVED, "Resolved"),
        (STATUS_SCHEDULED, "Scheduled"),
        (STATUS_IN_PROGRESS, "In Progress"),
        (STATUS_COMPLETED, "Completed"),
    ]

    title = models.CharField(max_length=200)
    post_type = models.CharField(max_length=20, choices=POST_TYPE_CHOICES)
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    reported_at = models.DateTimeField(null=True, blank=True)
    href = models.URLField(unique=True)
    raw_payload = models.JSONField()

    class Meta:
        ordering = ["-modified"]
        verbose_name = "Pager Duty Status Page Event"
        verbose_name_plural = "Pager Duty Status Page Events"

    def __str__(self):
        return f"[{self.post_type.upper()}] {self.title}"

    @property
    def label_colour(self):
        return {
            self.POST_TYPE_MAINTENANCE: self.MAINTENANCE_COLOUR,
            self.POST_TYPE_INCIDENT: self.INCIDENT_COLOUR,
        }.get(self.post_type, self.POST_TYPE_INCIDENT)

    @property
    def is_maintenance(self):
        return self.post_type == self.POST_TYPE_MAINTENANCE

    @property
    def is_incident(self):
        return self.post_type == self.POST_TYPE_INCIDENT

    @property
    def reported_at_local(self):
        return format_uk_time(self.reported_at)

    @property
    def starts_at_local(self):
        return format_uk_time(self.starts_at)

    @property
    def ends_at_local(self):
        return format_uk_time(self.ends_at)
