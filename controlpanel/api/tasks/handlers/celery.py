from celery import Task as CeleryTask

from controlpanel import celery_app
from controlpanel.api import cluster
from controlpanel.api.models import App, User, S3Bucket, UserS3Bucket, AppS3Bucket, Task


class BaseTaskHandler(CeleryTask):

    model = None
    # can be applied to project settings
    # these settings mean that messages are only removed from the queue (acknowledged)
    # when returned. if an error occurs, they remain in the queue, and will be resent
    # to the worker when the "visibility_timeout" has expired. "visibility_timeout" is
    # a setting that is configured in SQS per queue. Currently set to 30secs
    acks_late = True
    acks_on_failure_or_timeout = False

    def get_object(self, pk):
        try:
            return self.model.objects.get(pk=pk)
        except self.model.DoesNotExist as exc:
            print(exc)
            raise exc

    def get_user(self, pk):
        try:
            return User.objects.get(pk=pk)
        except User.DoesNotExist as exc:
            print(exc)
            raise exc

    def complete(self):
        task = Task.objects.filter(task_id=self.request.id).first()
        if task:
            task.completed = True
            task.save()


class CreateAppAuthSettings(BaseTaskHandler):
    model = App
    name = "create_app_auth_settings"

    def run(self, app_pk, user_pk, envs, disable_authentication, connections):
        app = self.get_object(pk=app_pk)
        user = self.get_user(pk=user_pk)
        if not user.github_api_token:
            return

        for env in envs:
            cluster.App(app, user.github_api_token).create_auth_settings(
                env_name=env,
                disable_authentication=disable_authentication,
                connections=connections,
            )
        self.complete()


class CreateS3Bucket(BaseTaskHandler):

    model = S3Bucket
    name = "create_s3bucket"

    def run(self, bucket_pk, user_pk, bucket_owner="APP"):
        bucket = self.get_object(pk=bucket_pk)
        # this will already have run when the obj was created via modelform validation.
        # Is it unnecessary to call again?
        if cluster.S3Bucket(bucket).exists(bucket.name, bucket_owner=bucket_owner):
            return

        # TODO verify user?

        bucket.cluster.create(owner=bucket_owner)


class CreateAppAWSRole(BaseTaskHandler):
    model = App
    name = "create_app_aws_role"

    def run(self, app_pk, user_pk):
        app = self.get_object(pk=app_pk)

        # TODO verify user?
        # user = self.get_user(pk=user_pk)

        cluster.App(app).create_iam_role()
        self.complete()


class GrantAppS3BucketAccess(BaseTaskHandler):

    model = AppS3Bucket
    name = 'grant_app_s3bucket_access'

    def run(self, app_s3_bucket_pk, user_pk):
        app_bucket = self.get_object(pk=app_s3_bucket_pk)

        # TODO verify user?

        cluster.App(app_bucket.app).grant_bucket_access(
            app_bucket.s3bucket.arn,
            app_bucket.access_level,
            app_bucket.resources,
        )


class GrantUserS3BucketAccess(BaseTaskHandler):

    model = UserS3Bucket
    name = "grant_user_s3bucket_access"

    def run(self, bucket_pk, user_pk):
        user_bucket = self.get_object(pk=bucket_pk)
        user = self.get_user(pk=user_pk)

        # TODO verify user?

        cluster.User(user).grant_bucket_access(
            user_bucket.s3bucket.arn,
            user_bucket.access_level,
            user_bucket.resources,
        )


create_app_aws_role = celery_app.register_task(CreateAppAWSRole())
create_s3bucket = celery_app.register_task(CreateS3Bucket())
grant_app_s3bucket_access = celery_app.register_task(GrantAppS3BucketAccess())
grant_user_s3bucket_access = celery_app.register_task(GrantUserS3BucketAccess())
create_app_auth_settings = celery_app.register_task(CreateAppAuthSettings())
