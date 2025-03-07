# Standard library
from urllib.parse import urlencode

# Third-party
from django.conf import settings
from django.contrib.auth.models import User
from django.core.validators import MinLengthValidator
from django.db import models
from django.db.models import Q
from django.db.transaction import atomic
from django.urls import reverse
from django.utils import timezone
from django_extensions.db.models import TimeStampedModel

# First-party/Local
from controlpanel.api import cluster, tasks, validators
from controlpanel.api.models.apps3bucket import AppS3Bucket
from controlpanel.api.models.users3bucket import UserS3Bucket


def s3bucket_console_url(name):
    region = settings.BUCKET_REGION
    args = urlencode(
        {
            "destination": f"/s3/buckets/{name}/?region={region}&tab=overview",
        }
    )
    return f"{settings.AWS_SERVICE_URL}/?{args}"


class S3BucketQuerySet(models.QuerySet):
    def accessible_by(self, user):
        return self.filter(Q(users3buckets__user=user) | Q(policys3buckets__policy__users=user))

    def administered_by(self, user):
        return self.filter(
            users3buckets__user=user,
            users3buckets__is_admin=True,
        )


class S3Bucket(TimeStampedModel):
    name = models.CharField(
        unique=True,
        max_length=100,
        validators=[
            validators.validate_env_prefix,
            validators.validate_s3_bucket_labels,
            MinLengthValidator(limit_value=3),
        ],
    )
    created_by = models.ForeignKey(
        "User",
        on_delete=models.SET_NULL,
        null=True,
    )
    is_data_warehouse = models.BooleanField(default=False)
    # TODO remove this field - it's unused
    location_url = models.CharField(max_length=128, null=True)
    is_deleted = models.BooleanField(default=False)
    deleted_by = models.ForeignKey(
        "User", on_delete=models.SET_NULL, null=True, related_name="deleted_s3buckets"
    )
    deleted_at = models.DateTimeField(null=True)

    objects = S3BucketQuerySet.as_manager()

    class Meta:
        db_table = "control_panel_api_s3bucket"
        ordering = ("name",)

    def __init__(self, *args, **kwargs):
        """Overwrite this constructor to pass some non-field parameter"""
        self.bucket_owner = kwargs.pop("bucket_owner", cluster.AWSRoleCategory.user)
        super().__init__(*args, **kwargs)

    def __repr__(self):
        warehouse = ""
        if self.is_data_warehouse:
            warehouse = " (warehouse)"
        return f"<{self.__class__.__name__}: {self.name}{warehouse}>"

    @property
    def cluster(self):
        if self.is_folder:
            return cluster.S3Folder(self)
        return cluster.S3Bucket(self)

    @property
    def arn(self):
        return self.cluster.arn

    def arn_from_path(self, path):
        return f"{self.arn}{path}"

    @property
    def aws_url(self):
        return s3bucket_console_url(self.name)

    @property
    def is_used_for_app(self):
        return not (AppS3Bucket.objects.filter(s3bucket_id=self.id).first() is None)

    @property
    def is_folder(self):
        """
        Determines if the datasource is a folder or S3 bucket. We store the name of a
        folder including the root bucket name, separated by a forward slash, and by
        convention a bucket name cannot contain a '/'. So if one is present in the name
        it must represent a folder.
        """
        return "/" in self.name

    def get_absolute_revoke_self_url(self):
        """
        Build url to the view which revokes the current user's access to the datasource.
        """
        return reverse("revoke-datasource-access-self", kwargs={"pk": self.pk})

    def user_is_admin(self, user):
        return (
            self.users3buckets.filter(
                user=user,
                is_admin=True,
            ).count()
            != 0
        )

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
        if not is_create:
            return self

        tasks.S3BucketCreate(
            entity=self,
            user=self.created_by,
            extra_data={
                "bucket_owner": kwargs.pop("bucket_owner", self.bucket_owner),
            },
        ).create_task()

        # created_by should always be set, but this is a failsafe
        if self.created_by:
            UserS3Bucket.objects.create(
                user=self.created_by,
                current_user=self.created_by,
                s3bucket=self,
                is_admin=True,
                access_level=UserS3Bucket.READWRITE,
            )

        return self

    @atomic
    def delete(self, *args, **kwargs):
        # TODO update when deletion is enabled for folders
        if not self.is_folder:
            self.cluster.mark_for_archival()
        super().delete(*args, **kwargs)

    def soft_delete(self, deleted_by: User):
        """
        Mark the object as deleted, but do not remove it from the database
        """
        self.is_deleted = True
        self.deleted_by = deleted_by
        self.deleted_at = timezone.now()
        self.save()
        # TODO update to handle deleting folders
        if self.is_folder:
            tasks.S3BucketArchive(self, self.deleted_by).create_task()
        else:
            self.cluster.mark_for_archival()

        tasks.S3BucketRevokeAllAccess(self, self.deleted_by).create_task()
