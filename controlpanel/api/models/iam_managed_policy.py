from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models
from django_extensions.db.models import TimeStampedModel

from controlpanel.api.aws import arn
from controlpanel.api import cluster


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
        return f"/{settings.ENV}/cpanel/"

    name = models.CharField(
        max_length=63,
        validators=[RegexValidator(r"[a-zA-Z0-9_-]{1,63}")]
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

        current_users = [
            r["RoleName"] for r in
            cluster.list_entities_for_policy(self.arn).get('PolicyRoles', [])
        ]
        user_names = [u.iam_role_name for u in self.users.all()]
        users_set = {*current_users, *user_names}

        for user_name in users_set:
            if user_name not in current_users:
                cluster.attach_policy_to_role(self.arn, user_name)
            elif user_name not in user_names:
                cluster.detach_policy_from_role(self.arn, user_name)

        return self

    def delete(self, *args, **kwargs):
        cluster.delete_policy(self.arn)
        super().delete(*args, **kwargs)
