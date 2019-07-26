from django.db import models
from django_extensions.db.models import TimeStampedModel

from controlpanel.api.cluster import S3AccessPolicy


class AccessToS3Bucket(TimeStampedModel):
    """
    Abstract model to model access to S3 buckets

    These models will be associated with an s3bucket and have
    an access level (`readonly` or `readwrite`)
    """

    READONLY = 'readonly'
    READWRITE = 'readwrite'

    ACCESS_LEVELS = (
        (READONLY, "Read-only"),
        (READWRITE, "Read-write"),
    )

    s3bucket = models.ForeignKey(
        "S3Bucket", related_name='%(class)ss', on_delete=models.CASCADE)
    access_level = models.CharField(
        max_length=9, choices=ACCESS_LEVELS, default=READONLY)

    class Meta:
        abstract = True

    def has_readwrite_access(self):
        return self.access_level == self.READWRITE

    def aws_role_name(self):
        raise NotImplementedError

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        with S3AccessPolicy.load(self.aws_role_name()) as policy:
            policy.grant_access(self.s3bucket.arn, self.access_level)

        return self

    def delete(self, *args, **kwargs):
        with S3AccessPolicy.load(self.aws_role_name()) as policy:
            policy.revoke_access(self.s3bucket.arn)

        super().delete(*args, **kwargs)

