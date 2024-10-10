# Standard library
import base64
import json

# Third-party
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django_extensions.db.models import TimeStampedModel

# First-party/Local
from controlpanel.utils import send_sse


class Task(TimeStampedModel):
    """
    Use the task table to track the basic status of task fired from the app
    """

    entity_class = models.CharField(max_length=20)
    entity_description = models.CharField(max_length=128)
    entity_id = models.BigIntegerField()
    user_id = models.CharField(max_length=128)
    task_id = models.UUIDField(primary_key=True)
    task_name = models.CharField(max_length=60)
    task_description = models.CharField(max_length=128)
    queue_name = models.CharField(max_length=60)
    completed = models.BooleanField(default=False)
    cancelled = models.BooleanField(default=False)
    message_body = models.CharField(max_length=4000)
    retried_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "control_panel_api_task"
        ordering = ("-created",)

    def __repr__(self):
        return f"<Task: {self.entity_class}|{self.entity_id}|{self.task_name}|{self.task_id}>"

    @property
    def decoded_message_body(self):
        try:
            decoded = base64.b64decode(self.message_body)
            return json.loads(decoded)
        except Exception:
            return f"Cannot decode message body: {self.message_body}"

    @property
    def decoded_task_body(self):
        try:
            decoded = base64.b64decode(self.decoded_message_body["body"])
        except TypeError:
            return "No task body to decode"

        try:
            return json.loads(decoded)
        except Exception:
            return "Cannot decode task body"

    @property
    def status(self):
        if self.cancelled:
            return "CANCELLED"

        if self.completed:
            return "COMPLETED"

        if self.created > timezone.now() - timezone.timedelta(days=4):
            return "PENDING"

        if self.retried_at is None:
            return "FAILED"

        if self.retried_at > timezone.now() - timezone.timedelta(days=4):
            return "RETRYING"

        return "FAILED"

    def get_absolute_url(self):
        return reverse("task-detail", kwargs={"pk": self.pk})

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        if self.completed:
            payload = {
                "entity_name": self.entity_description,
                "task_description": self.task_description,
                "status": "COMPLETED",
            }
            send_sse(
                self.user_id,
                {
                    "event": "taskStatus",
                    "data": json.dumps(payload),
                },
            )
