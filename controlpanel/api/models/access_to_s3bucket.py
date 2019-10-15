import re

from django.contrib.postgres.fields import ArrayField
from django.core.validators import RegexValidator
from django.db import models
from django.dispatch import receiver
from django_extensions.db.models import TimeStampedModel

from controlpanel.api import cluster
from controlpanel.api.models.iam_managed_policy import IAMManagedPolicy


S3BUCKET_PATH_PATTERN = r"[a-zA-Z0-9_/\*-]"
S3BUCKET_PATH_REGEX = re.compile(S3BUCKET_PATH_PATTERN)


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
    paths = ArrayField(
        models.CharField(
            max_length=255,
            validators=[RegexValidator(S3BUCKET_PATH_PATTERN)],
        ),
        default=list,
    )

    class Meta:
        abstract = True

    def has_readwrite_access(self):
        return self.access_level == self.READWRITE

    @property
    def iam_role_name(self):
        raise NotImplementedError

    def grant_bucket_access(self):
        raise NotImplementedError

    def revoke_bucket_access(self):
        raise NotImplementedError

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.grant_bucket_access()
        return self

    def delete(self, *args, **kwargs):
        self.revoke_bucket_access()
        super().delete(*args, **kwargs)

    @property
    def resources(self):
        resources = [self.s3bucket.arn_from_path(p) for p in self.paths]
        return resources or [self.s3bucket.arn]


# MUST use signals because cascade deletes do not call delete()
@receiver(models.signals.pre_delete)
def revoke_access(sender, **kwargs):
    if issubclass(sender, AccessToS3Bucket):
        obj = kwargs['instance']
        obj.revoke_bucket_access()

