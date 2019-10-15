from django.db import models

from controlpanel.api.models.access_to_s3bucket import AccessToS3Bucket


class PolicyS3Bucket(AccessToS3Bucket):
    """
    Similar to UserS3Bucket but with groups
    """
    policy = models.ForeignKey(
        "IAMManagedPolicy",
        related_name="policys3buckets",
        on_delete=models.CASCADE
    )

    class Meta:
        db_table = "control_panel_api_policys3bucket"
        unique_together = ("policy", "s3bucket")
        ordering = ("id",)

    @property
    def aws_name(self):
        return self.policy.arn

    def grant_bucket_access(self):
        cluster.Group(self.policy).grant_bucket_access(
            self.s3bucket.arn,
            self.access_level,
        )

    def revoke_bucket_access(self):
        cluster.Group(self.policy).revoke_bucket_access(self.s3bucket.arn)

