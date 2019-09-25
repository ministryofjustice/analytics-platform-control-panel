import re

from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models
from django_extensions.db.models import TimeStampedModel

from controlpanel.api.aws import arn
from controlpanel.api import cluster


POLICY_NAME_PATTERN = r"[a-z0-9_+@,.:=-]{2,63}"
POLICY_NAME_REGEX = re.compile(POLICY_NAME_PATTERN)


class IAMManagedPolicy(TimeStampedModel):
    @property
    def arn(self):
        return arn(
            "iam",
            f"policy{self.path}{self.name}",
            account=settings.AWS_ACCOUNT_ID
        )

    @property
    def path(self):
        return f"/{settings.ENV}/group/"

    name = models.CharField(
        max_length=63,
        validators=[RegexValidator(POLICY_NAME_PATTERN)],
        unique=True
    )
    users = models.ManyToManyField("User")
    created_by = models.ForeignKey(
        "User",
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_by_iam_managed_policy"
    )

    class Meta(TimeStampedModel.Meta):
        db_table = "control_panel_api_iam_managed_policy"

    def save(self, *args, **kwargs):
        is_create = not self.pk

        super().save(*args, **kwargs)

        if is_create:
            cluster.create_policy(
                self.name,
                self.path
            )

        stored_roles = {u.iam_role_name for u in self.users.all()}

        cluster.update_policy_roles(self.arn, stored_roles)

        return self

    def delete(self, *args, **kwargs):
        cluster.delete_policy(self.arn)
        super().delete(*args, **kwargs)
