from django.db import models

from controlpanel.api.cluster import S3AccessPolicy
from controlpanel.api.models.access_to_s3bucket import AccessToS3Bucket


class AppS3Bucket(AccessToS3Bucket):
    """
    An app (potentially) has access to several S3 buckets.

    We have two access levels, "readonly" (default) and "readwrite".
    """
    policy_class = S3AccessPolicy

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

    def aws_name(self):
        return self.app.iam_role_name

    def __repr__(self):
        return f'<AppS3Bucket: {self.app!r} {self.s3bucket!r} {self.access_level}>'

