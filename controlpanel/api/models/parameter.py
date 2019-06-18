from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models
from django.db.models.signals import pre_delete, pre_save
from django.dispatch import receiver

from django_extensions.db.models import TimeStampedModel

from controlpanel.api.aws import aws, arn


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


@receiver(pre_save, sender=Parameter)
def save_aws_parameter(sender, **kwargs):
    parameter = kwargs['instance']
    is_create = not parameter.pk

    if is_create:
        aws.create_parameter(
            parameter.name,
            parameter.value,
            parameter.role_name,
            description=parameter.description
        )


@receiver(pre_delete, sender=Parameter)
def delete_aws_parameter(sender, **kwargs):
    parameter = kwargs['instance']
    aws.delete_parameter(
        parameter.name
    )
