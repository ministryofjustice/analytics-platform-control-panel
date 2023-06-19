# Third-party
from django.db import models

# First-party/Local
from controlpanel.api import cluster
from controlpanel.api.models.access_to_s3bucket import AccessToS3Bucket


# TODO rename this to RoleGroupS3Bucket
class PolicyS3Bucket(AccessToS3Bucket):
    """
    Similar to UserS3Bucket but with groups
    """

    policy = models.ForeignKey(
        "IAMManagedPolicy", related_name="policys3buckets", on_delete=models.CASCADE
    )

    class Meta:
        db_table = "control_panel_api_policys3bucket"
        unique_together = ("policy", "s3bucket")
        ordering = ("id",)

    def grant_bucket_access(self):
        if self.s3bucket.is_folder:
            return cluster.RoleGroup(self.policy).grant_folder_access(
                self.s3bucket.arn,
                self.access_level,
                self.resources,
            )
        cluster.RoleGroup(self.policy).grant_bucket_access(
            self.s3bucket.arn,
            self.access_level,
            self.resources,
        )

    def revoke_bucket_access(self):
        cluster.RoleGroup(self.policy).revoke_bucket_access(self.s3bucket.arn)
