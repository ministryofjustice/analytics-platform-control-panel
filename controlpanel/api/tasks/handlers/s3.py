# First-party/Local
from controlpanel.api import cluster
from controlpanel.api.models import AppS3Bucket, S3Bucket, UserS3Bucket
from controlpanel.api.tasks.handlers.base import BaseModelTaskHandler


class CreateS3Bucket(BaseModelTaskHandler):
    model = S3Bucket
    name = "create_s3bucket"
    permission_required = "api.create_s3bucket"

    def run_task(self, bucket, user, bucket_owner=None):
        bucket_owner = bucket_owner or "USER"
        bucket.cluster.create(owner=bucket_owner)
        self.complete()


class GrantAppS3BucketAccess(BaseModelTaskHandler):
    model = AppS3Bucket
    name = 'grant_app_s3bucket_access'
    permission_required = 'api.create_apps3bucket'

    def run_task(self, app_bucket, user):
        cluster.App(app_bucket.app).grant_bucket_access(
            app_bucket.s3bucket.arn,
            app_bucket.access_level,
            app_bucket.resources,
        )
        self.complete()


class GrantUserS3BucketAccess(BaseModelTaskHandler):
    model = UserS3Bucket
    name = "grant_user_s3bucket_access"
    permission_required = "api.create_users3bucket"

    def run_task(self, user_bucket, user):
        if user_bucket.s3bucket.is_folder:
            print(f"GRANTING {user_bucket.access_level} ACCESS TO A FOLDER FOR {user}")
            cluster.User(user_bucket.user).grant_folder_access(
                root_folder_path=user_bucket.s3bucket.name,
                access_level=user_bucket.access_level,
                paths=user_bucket.paths,
            )
        else:
            print(f"GRANTING {user_bucket.access_level} ACCESS TO A BUCKET FOR {user}")
            cluster.User(user_bucket.user).grant_bucket_access(
                user_bucket.s3bucket.arn,
                user_bucket.access_level,
                user_bucket.resources,
            )
        self.complete()
