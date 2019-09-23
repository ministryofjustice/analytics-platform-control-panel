from django.db import models

from controlpanel.api.cluster import S3ManagedPolicy
from controlpanel.api.models.access_to_s3bucket import AccessToS3Bucket


class PolicyS3Bucket(AccessToS3Bucket):
    """
    Similar to UserS3Bucket but with groups
    """
    policy_class = S3ManagedPolicy

    policy = models.ForeignKey(
        "IAMManagedPolicy",
        related_name="policys3buckets",
        on_delete=models.CASCADE
    )

    class Meta:
        db_table = "control_panel_api_policys3bucket"
        unique_together = ("policy", "s3bucket")
        ordering = ("id",)

    def aws_name(self):
        return self.policy.arn
