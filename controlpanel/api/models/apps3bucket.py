# Third-party
from django.db import models

# First-party/Local
from controlpanel.api import cluster, tasks
from controlpanel.api.models.access_to_s3bucket import AccessToS3Bucket


class AppS3Bucket(AccessToS3Bucket):
    """
    An app (potentially) has access to several S3 buckets.

    We have two access levels, "readonly" (default) and "readwrite".
    """

    app = models.ForeignKey(
        "App",
        related_name="apps3buckets",
        on_delete=models.CASCADE,
    )

    # Non database field just for passing extra parameters
    current_user = None

    class Meta:
        db_table = "control_panel_api_apps3bucket"
        # one record per app/s3bucket
        unique_together = ("app", "s3bucket")
        ordering = ("id",)

    def __init__(self, *args, **kwargs):
        """Overwrite this constructor to pass some non-field parameter"""
        self.current_user = kwargs.pop("current_user", None)
        super().__init__(*args, **kwargs)

    @property
    def iam_role_name(self):
        return self.app.iam_role_name

    def __repr__(self):
        return f"<AppS3Bucket: {self.app!r} {self.s3bucket!r} {self.access_level}>"

    def grant_bucket_access(self):
        tasks.S3BucketGrantToApp(self, self.current_user).create_task()

    def revoke_bucket_access(self, revoked_by=None):
        revoked_by = revoked_by or None
        tasks.S3BucketRevokeAppAccess(self, revoked_by).create_task()
