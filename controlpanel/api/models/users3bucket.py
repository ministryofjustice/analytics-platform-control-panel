# Third-party
from django.db import models

# First-party/Local
from controlpanel.api import cluster, tasks
from controlpanel.api.models.access_to_s3bucket import AccessToS3Bucket


class UserS3Bucket(AccessToS3Bucket):
    """
    A user can have access to several S3 buckets.

    We have two access levels, "readonly" (default) and "readwrite".
    The `is_admin` field determine if the user has admin privileges on the
    S3 bucket
    """

    user = models.ForeignKey(
        "User", related_name="users3buckets", on_delete=models.CASCADE
    )
    is_admin = models.BooleanField(default=False)

    # Non database field just for passing extra parameters
    current_user = None

    class Meta:
        db_table = "control_panel_api_users3bucket"
        # one record per user/s3bucket
        unique_together = ("user", "s3bucket")
        ordering = ("id",)

    def __init__(self, *args, **kwargs):
        """Overwrite this constructor to pass some non-field parameter"""
        self.current_user = kwargs.pop("current_user", None)
        self.send_task = kwargs.pop("send_task", True)
        super().__init__(*args, **kwargs)

    @property
    def iam_role_name(self):
        return self.user.iam_role_name

    def __repr__(self):
        return (
            f"<UserS3Bucket: {self.user!r} {self.s3bucket!r} {self.access_level}"
            f'{" admin" if self.is_admin else ""}>'
        )

    def grant_bucket_access(self):
        """
        If send_task is False, granting permission must be handled elsewhere. This may
        be because we are using a database transaction and want all objects to be
        created before sending the task to grant access.
        """
        if self.send_task:
            tasks.S3BucketGrantToUser(self, self.current_user).create_task()

    def revoke_bucket_access(self):
        tasks.S3BucketRevokeUserAccess(self).create_task()
