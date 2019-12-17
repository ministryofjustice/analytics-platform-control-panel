from django.db import models

from controlpanel.api import cluster
from controlpanel.api.models.access_to_s3bucket import AccessToS3Bucket


class UserS3Bucket(AccessToS3Bucket):
    """
    A user can have access to several S3 buckets.

    We have two access levels, "readonly" (default) and "readwrite".
    The `is_admin` field determine if the user has admin privileges on the
    S3 bucket
    """
    user = models.ForeignKey(
        "User",
        related_name='users3buckets',
        on_delete=models.CASCADE
    )
    is_admin = models.BooleanField(default=False)

    class Meta:
        db_table = "control_panel_api_users3bucket"
        # one record per user/s3bucket
        unique_together = ('user', 's3bucket')
        ordering = ('id',)

    @property
    def iam_role_name(self):
        return self.user.iam_role_name

    def __repr__(self):
        return (
            f'<UserS3Bucket: {self.user!r} {self.s3bucket!r} {self.access_level}'
            f'{" admin" if self.is_admin else ""}>'
        )

    def grant_bucket_access(self):
        cluster.User(self.user).grant_bucket_access(
            self.s3bucket.arn,
            self.access_level,
            self.resources,
        )

    def revoke_bucket_access(self):
        cluster.User(self.user).revoke_bucket_access(self.s3bucket.arn)

