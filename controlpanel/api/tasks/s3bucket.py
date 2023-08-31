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


class S3BucketGrantToUser(TaskBase):
    ENTITY_CLASS = "UserS3Bucket"

    @property
    def task_name(self):
        return "grant_user_s3bucket_access"

    @property
    def task_description(self):
        return "granting access to the user"

    @property
    def entity_description(self):
        return self.entity.s3bucket.name


class S3BucketGrantToApp(TaskBase):
    ENTITY_CLASS = "AppS3Bucket"

    @property
    def task_name(self):
        return "grant_app_s3bucket_access"

    @property
    def task_description(self):
        return "granting access to the app"

    @property
    def entity_description(self):
        return self.entity.s3bucket.name
