from django.db import models
from django_extensions.db.models import TimeStampedModel


class Role(TimeStampedModel):
    name = models.CharField(max_length=256, blank=False, unique=True)
    code = models.CharField(max_length=256, blank=False, unique=True)

    class Meta:
        db_table = "control_panel_api_role"
        ordering = ('name',)
