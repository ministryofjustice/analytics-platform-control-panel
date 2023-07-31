from controlpanel.api.tasks.task_base import TaskBase


class S3BucketCreate(TaskBase):
    ENTITY_CLASS = "S3Bucket"
    QUEUE_NAME = "s3_queue"

    @property
    def task_name(self):
        return "controlpanel.celery.create_s3bucket"

    @property
    def task_description(self):
        return "creating s3 bucket"


class S3BucketGrantToUser(TaskBase):
    ENTITY_CLASS = "UserS3Bucket"
    QUEUE_NAME = "iam_queue"

    @property
    def task_name(self):
        return "controlpanel.celery.s3bucket_grant_to_user"

    @property
    def task_description(self):
        return "granting access to the user"


class S3BucketGrantToApp(TaskBase):
    ENTITY_CLASS = "AppS3Bucket"
    QUEUE_NAME = "iam_queue"

    @property
    def task_name(self):
        return "controlpanel.celery.s3bucket_grant_to_app"

    @property
    def task_description(self):
        return "granting access to the app"


class S3BucketRevokeFromUser(TaskBase):
    ENTITY_CLASS = "UserS3Bucket"
    QUEUE_NAME = "iam_queue"

    @property
    def task_name(self):
        return "controlpanel.celery.s3bucket_revoke_from_user"

    @property
    def task_description(self):
        return "revoking access from the user"


class S3BucketRevokeFromApp(TaskBase):
    ENTITY_CLASS = "AppS3Bucket"
    QUEUE_NAME = "iam_queue"

    @property
    def task_name(self):
        return "controlpanel.celery.s3bucket_from_app"

    @property
    def task_description(self):
        return "revoking access from the app"
