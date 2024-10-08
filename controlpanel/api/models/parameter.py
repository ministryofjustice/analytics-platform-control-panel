# Third-party
from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models
from django_extensions.db.models import TimeStampedModel

# First-party/Local
from controlpanel.api import cluster
from controlpanel.api.aws import arn

APP_TYPE_AIRFLOW = "airflow"
APP_TYPE_CHOICES = ((APP_TYPE_AIRFLOW, "Airflow"),)


class ParameterQuerySet(models.QuerySet):

    def airflow(self):
        return self.filter(app_type=APP_TYPE_AIRFLOW)


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

    key = models.CharField(max_length=50, validators=[RegexValidator(r"[a-zA-Z0-9_]{1,50}")])
    description = models.CharField(max_length=600)
    # legacy field as all parameters should now be for airflow, but there may be some for apps
    # remaining that will need to be cleared up. Then this field can be removed
    app_type = models.CharField(max_length=8, choices=APP_TYPE_CHOICES, default=APP_TYPE_AIRFLOW)
    role_name = models.CharField(max_length=63, validators=[RegexValidator(r"[a-zA-Z0-9_]{1,63}")])
    created_by = models.ForeignKey(
        "User",
        on_delete=models.SET_NULL,
        null=True,
    )

    objects = ParameterQuerySet.as_manager()

    class Meta(TimeStampedModel.Meta):
        db_table = "control_panel_api_parameter"

    def save(self, *args, **kwargs):
        is_create = not self.pk

        super().save(*args, **kwargs)

        if is_create:
            cluster.AppParameter(self).create_parameter()

        return self

    def delete(self, *args, **kwargs):
        cluster.AppParameter(self).delete_parameter()
        super().delete(*args, **kwargs)
