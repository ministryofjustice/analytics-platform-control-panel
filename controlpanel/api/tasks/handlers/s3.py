# Third-party
from celery import Task as CeleryTask

# First-party/Local
from controlpanel.api import cluster
from controlpanel.api.models import App, AppS3Bucket, S3Bucket, User, UserS3Bucket
from controlpanel.api.tasks.handlers.base import BaseModelTaskHandler, BaseTaskHandler


class CreateS3Bucket(BaseModelTaskHandler):
    model = S3Bucket
    name = "create_s3bucket"

    def handle(self, bucket_owner=None):
        bucket_owner = bucket_owner or "USER"
        self.object.cluster.create(owner=bucket_owner)
        self.complete()


class GrantAppS3BucketAccess(BaseModelTaskHandler):
    model = AppS3Bucket
    name = 'grant_app_s3bucket_access'

    def handle(self):
        cluster.App(self.object.app).grant_bucket_access(
            self.object.s3bucket.arn,
            self.object.access_level,
            self.object.resources,
        )
        self.complete()


class GrantUserS3BucketAccess(BaseModelTaskHandler):
    model = UserS3Bucket
    name = "grant_user_s3bucket_access"

    def handle(self):
        if self.object.s3bucket.is_folder:
            cluster.User(self.object.user).grant_folder_access(
                root_folder_path=self.object.s3bucket.name,
                access_level=self.object.access_level,
                paths=self.object.paths,
            )
        else:
            cluster.User(self.object.user).grant_bucket_access(
                bucket_arn=self.object.s3bucket.arn,
                access_level=self.object.access_level,
                path_arns=self.object.resources,
            )
        self.complete()


class S3BucketRevokeUserAccess(BaseTaskHandler):
    name = "revoke_user_s3bucket_access"

    def handle(self, bucket_identifier, bucket_user_pk, is_folder):
        bucket_user = User.objects.get(pk=bucket_user_pk)
        if is_folder:
            cluster.User(bucket_user).revoke_folder_access(bucket_identifier)
        else:
            cluster.User(bucket_user).revoke_bucket_access(bucket_identifier)
        self.complete()


class S3BucketRevokeAppAccess(BaseTaskHandler):
    name = "revoke_app_s3bucket_access"

    def handle(self, bucket_arn, app_pk):
        try:
            app = App.objects.get(pk=app_pk)
        except App.DoesNotExist:
            # if the app doesnt exist, nothing to revoke, so mark completed
            self.complete()
        cluster.App(app).revoke_bucket_access(bucket_arn)
        self.complete()
