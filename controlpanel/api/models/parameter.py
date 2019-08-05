from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models

from django_extensions.db.models import TimeStampedModel

from controlpanel.api.aws import arn
from controlpanel.api import cluster


APP_TYPE_CHOICES = (
    ('airflow', 'Airflow'),
    ('webapp', 'Web app'),
)


class Parameter(TimeStampedModel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._value = None

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, val):
        self._value = val

    @property
    def arn(self):
        return arn("ssm", f"parameter{self.name}")

    @property
    def name(self):
        return f"/{settings.ENV}/{self.app_type}/{self.role_name}/secrets/{self.key}"

    key = models.CharField(
        max_length=50,
        validators=[RegexValidator(r'[a-zA-Z0-9_]{1,50}')]
    )
    description = models.CharField(max_length=600)
    app_type = models.CharField(
        max_length=8,
        choices=APP_TYPE_CHOICES
    )
    role_name = models.CharField(
        max_length=63,
        validators=[RegexValidator(r'[a-zA-Z0-9_]{1,63}')]
    )
    created_by = models.ForeignKey(
        "User",
        on_delete=models.SET_NULL,
        null=True,
    )

    class Meta(TimeStampedModel.Meta):
        db_table = "control_panel_api_parameter"

    def save(self, *args, **kwargs):
        is_create = not self.pk

        super().save(*args, **kwargs)

        if is_create:
            cluster.create_parameter(
                self.name,
                self.value,
                self.role_name,
                self.description,
            )

        return self

    def delete(self, *args, **kwargs):
        cluster.delete_parameter(self.name)
        super().delete(*args, **kwargs)
