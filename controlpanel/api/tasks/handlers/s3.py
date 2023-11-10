# Third-party
import structlog
from django.db.models.deletion import Collector

# First-party/Local
from controlpanel.api import cluster, tasks
from controlpanel.api.models import App, AppS3Bucket, S3Bucket, User, UserS3Bucket
from controlpanel.api.models.access_to_s3bucket import AccessToS3Bucket
from controlpanel.api.tasks.handlers.base import BaseModelTaskHandler, BaseTaskHandler

log = structlog.getLogger(__name__)


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


class S3BucketRevokeAllAccess(BaseModelTaskHandler):
    model = S3Bucket
    name = "s3bucket_revoke_all_access"

    def handle(self, *args, **kwargs):
        """
        When an S3Bucket is soft-deleted, the related objects that handle access will
        remain in place. In order to keep IAM roles updated, this task collects objects
        that would have been deleted by a cascade, and revokes access to deleted bucket
        """
        task_user = User.objects.filter(pk=self.task_user_pk).first()
        collector = Collector(using="default")
        collector.collect([self.object])
        for model, instance in collector.instances_with_model():
            if not issubclass(model, AccessToS3Bucket):
                continue

            instance.current_user = task_user
            instance.revoke_bucket_access()

        self.complete()


class ArchiveS3Bucket(BaseModelTaskHandler):
    model = S3Bucket
    name = "archive_s3bucket"

    def handle(self, *args, **kwargs):
        task_user = User.objects.filter(pk=self.task_user_pk).first()
        for s3obj in cluster.S3Folder(self.object).get_objects():
            tasks.S3BucketArchiveObject(
                self.object, task_user, extra_data={"s3obj_key": s3obj.key}
            ).create_task()
        self.complete()


class ArchiveS3Object(BaseModelTaskHandler):
    model = S3Bucket
    name = "archive_s3_object"

    def handle(self, s3obj_key):
        # TODO update to use self.object.cluster to work with buckets
        cluster.S3Folder(self.object).archive_object(key=s3obj_key)
        self.complete()
