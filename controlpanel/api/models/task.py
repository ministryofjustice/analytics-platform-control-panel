import json

# Third-party
from django.db import models
from django_extensions.db.models import TimeStampedModel

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
    message_body = models.CharField(max_length=4000)

    class Meta:
        db_table = "control_panel_api_task"
        ordering = ("entity_class", "entity_id")

    def __repr__(self):
        return f"<Task: {self.entity_class}|{self.entity_id}|{self.task_name}|{self.task_id}>"

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


