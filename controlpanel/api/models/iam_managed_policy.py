# Standard library
import re

# Third-party
from django.core.validators import RegexValidator
from django.db import models
from django_extensions.db.models import TimeStampedModel

# First-party/Local
from controlpanel.api import cluster

POLICY_NAME_PATTERN = r"[a-z0-9_+@,.:=-]{2,63}"
POLICY_NAME_REGEX = re.compile(POLICY_NAME_PATTERN)


# TODO rename this to RoleGroup
class IAMManagedPolicy(TimeStampedModel):
    """Represents a group of users who have access to S3 resources"""

    name = models.CharField(
        max_length=63, validators=[RegexValidator(POLICY_NAME_PATTERN)], unique=True
    )
    users = models.ManyToManyField("User")
    created_by = models.ForeignKey(
        "User",
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_by_iam_managed_policy",
    )

    class Meta(TimeStampedModel.Meta):
        db_table = "control_panel_api_iam_managed_policy"

    @property
    def arn(self):
        return cluster.RoleGroup(self).arn

    @property
    def path(self):
        return cluster.RoleGroup(self).path

    def save(self, *args, **kwargs):
        is_create = not self.pk

        super().save(*args, **kwargs)

        group = cluster.RoleGroup(self)
        if is_create:
            group.create()

        group.update_members()

        return self

    def delete(self, *args, **kwargs):
        cluster.RoleGroup(self).delete()
        super().delete(*args, **kwargs)
