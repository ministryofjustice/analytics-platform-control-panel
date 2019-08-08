from urllib.parse import urlencode

from django.conf import settings
from django.db import models
from django_extensions.db.models import TimeStampedModel

from controlpanel.api import cluster, validators
from controlpanel.api.aws import s3_arn
from controlpanel.api.models.users3bucket import UserS3Bucket


def s3bucket_console_url(name):
    # TODO - remove hardcoded mojanalytics.xyz URL
    env = settings.ENV
    region = settings.BUCKET_REGION
    args = urlencode({
        "destination": f"/s3/buckets/{name}/?region={region}&tab=overview",
    })
    return f"https://aws.services.{env}.mojanalytics.xyz/?{args}"


class S3BucketQuerySet(models.QuerySet):
    def accessible_by(self, user):
        return self.filter(
            users3buckets__user=user,
        )

    def administered_by(self, user):
        return self.filter(
            users3buckets__user=user,
            users3buckets__is_admin=True,
        )


class S3Bucket(TimeStampedModel):
    name = models.CharField(unique=True, max_length=63, validators=[
        validators.validate_env_prefix,
        validators.validate_s3_bucket_length,
        validators.validate_s3_bucket_labels,
    ])
    created_by = models.ForeignKey(
        "User",
        on_delete=models.SET_NULL,
        null=True,
    )
    is_data_warehouse = models.BooleanField(default=False)
    location_url = models.CharField(max_length=128, null=True)

    objects = S3BucketQuerySet.as_manager()

    class Meta:
        db_table = "control_panel_api_s3bucket"
        ordering = ('name',)

    def __repr__(self):
        warehouse = ""
        if self.is_data_warehouse:
            warehouse = " (warehouse)"
        return f"<{self.__class__.__name__}: {self.name}{warehouse}>"

    @property
    def arn(self):
        return s3_arn(self.name)

    @property
    def aws_url(self):
        return s3bucket_console_url(self.name)

    def user_is_admin(self, user):
        return self.users3buckets.filter(
            user=user,
            is_admin=True,
        ).count() != 0

    def access_level(self, user):
        try:
            bucket_access = self.users3buckets.get(user=user)
            if bucket_access.is_admin:
                return "admin"
            return bucket_access.access_level

        except UserS3Bucket.DoesNotExist:
            pass

        return "None"

    def save(self, *args, **kwargs):
        is_create = not self.pk

        super().save(*args, **kwargs)

        if is_create:
            bucket = cluster.create_bucket(self.name, self.is_data_warehouse)
            if bucket:
                self.location_url = bucket['Location']

            # XXX created_by is always set if model is saved by the API view
            if self.created_by:
                UserS3Bucket.objects.create(
                    user=self.created_by,
                    s3bucket=self,
                    is_admin=True,
                    access_level=UserS3Bucket.READWRITE,
                )

        return self
