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

    def __init__(self, *args, **kwargs):
        self.current_user = kwargs.pop("current_user", None)
        super().__init__(*args, **kwargs)

    def grant_bucket_access(self):
        if self.s3bucket.is_folder:
            return cluster.RoleGroup(self.policy).grant_folder_access(
                root_folder_path=self.s3bucket.name,
                access_level=self.access_level,
                paths=self.paths,
            )
        cluster.RoleGroup(self.policy).grant_bucket_access(
            self.s3bucket.arn,
            self.access_level,
            self.resources,
        )

    def revoke_bucket_access(self):
        # TODO update to use a Task to revoke access, to match user/app access
        if self.s3bucket.is_folder:
            return cluster.RoleGroup(self.policy).revoke_folder_access(
                root_folder_path=self.s3bucket.name
            )

        cluster.RoleGroup(self.policy).revoke_bucket_access(self.s3bucket.arn)
