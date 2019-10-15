from django.db import models

from controlpanel.api import cluster
from controlpanel.api.models.access_to_s3bucket import AccessToS3Bucket


class AppS3Bucket(AccessToS3Bucket):
    """
    An app (potentially) has access to several S3 buckets.

    We have two access levels, "readonly" (default) and "readwrite".
    """
    app = models.ForeignKey(
        "App",
        related_name='apps3buckets',
        on_delete=models.CASCADE,
    )

    class Meta:
        db_table = "control_panel_api_apps3bucket"
        # one record per app/s3bucket
        unique_together = ('app', 's3bucket')
        ordering = ('id',)

    @property
    def iam_role_name(self):
        return self.app.iam_role_name

    def __repr__(self):
        return f'<AppS3Bucket: {self.app!r} {self.s3bucket!r} {self.access_level}>'

    def grant_bucket_access(self):
        cluster.App(self.app).grant_bucket_access(
            self.s3bucket.arn,
            self.access_level,
        )

    def revoke_bucket_access(self):
        cluster.App(self.app).revoke_bucket_access(self.s3bucket.arn)

