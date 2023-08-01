from django.conf import settings
from controlpanel.api.tasks.task_base import TaskBase


class S3BucketCreate(TaskBase):
    ENTITY_CLASS = "S3Bucket"
    # QUEUE_NAME = settings.S3_QUEUE_NAME

    @property
    def task_name(self):
        return "controlpanel.celery.create_s3bucket"

    @property
    def task_description(self):
        return "creating s3 bucket"


class S3BucketGrantToUser(TaskBase):
    ENTITY_CLASS = "UserS3Bucket"

    @property
    def task_name(self):
        return "controlpanel.celery.s3bucket_grant_to_user"

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
        return "controlpanel.celery.s3bucket_grant_to_app"

    @property
    def task_description(self):
        return "granting access to the app"

    @property
    def entity_description(self):
        return self.entity.s3bucket.name
