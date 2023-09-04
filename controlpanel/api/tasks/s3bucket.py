# Third-party
from django.conf import settings

# First-party/Local
from controlpanel.api.tasks.task_base import TaskBase


class S3BucketCreate(TaskBase):
    ENTITY_CLASS = "S3Bucket"
    QUEUE_NAME = settings.S3_QUEUE_NAME

    @property
    def task_name(self):
        return "create_s3bucket"

    @property
    def task_description(self):
        return "creating s3 bucket"

    def _get_args_list(self):
        return [
            self.entity.id,
            self.user.id if self.user else 'None',
            self.extra_data.get('bucket_owner'),
        ]


class S3AccessMixin:
    ACTION = None
    ROLE = None

    @property
    def task_name(self):
        return "{action}_{role}_s3bucket_access".format(
            action=self.ACTION.lower(),
            role=self.ROLE.lower()
        )

    @property
    def task_description(self):
        return "{action} access to the {role}".format(
            action=self.ACTION.lower(),
            role=self.ROLE.lower()
        )

    @property
    def entity_description(self):
        return self.entity.s3bucket.name


class S3BucketGrantToUser(S3AccessMixin, TaskBase):
    ENTITY_CLASS = "UserS3Bucket"
    ACTION = "GRANT"
    ROLE = "USER"


class S3BucketGrantToApp(S3AccessMixin, TaskBase):
    ENTITY_CLASS = "AppS3Bucket"
    ACTION = "GRANT"
    ROLE = "APP"


class S3BucketRevokeUserAccess(S3AccessMixin, TaskBase):
    ENTITY_CLASS = "UserS3Bucket"
    ACTION = "REVOKE"
    ROLE = "USER"

    def _get_args_list(self):
        bucket = self.entity.s3bucket
        return [
            bucket.name if bucket.is_folder else bucket.arn,
            self.entity.user.pk,
            bucket.is_folder,
        ]
