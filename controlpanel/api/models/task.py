import json

# Third-party
from django.apps import apps
from django.contrib.auth import get_user_model
from django.db import models
from django.utils.functional import cached_property
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

    @cached_property
    def entity_object(self):
        cls = apps.get_model(app_label="api", model_name=self.entity_class)
        try:
            return cls.objects.get(pk=self.entity_id)
        except cls.DoesNotExist:
            return None

    @property
    def user_object(self):
        return get_user_model().objects.get(pk=self.user_id)

    def resend(self):
        task_cls = self.entity_object.get_task_class(self.task_name)
        task = task_cls(self.entity_object, self.user_object)
        task.resend_task(task_id=self.task_id)
