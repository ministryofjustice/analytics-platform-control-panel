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
            # if the main object cannot be found, raise error and allow message to be
            # added back to the queue as could be due to a race condition
            raise exc

    def get_user(self, pk):
        try:
            return User.objects.get(pk=pk)
        except User.DoesNotExist as exc:
            # if the user is found, this should be a hard fail? So suggest log the error
            # and then mark as complete to stop task being rerun?
            return self.complete()

    def complete(self):
        task = Task.objects.filter(task_id=self.request.id).first()
        if task:
            task.completed = True
            task.save()


class CreateAppAuthSettings(BaseTaskHandler):
    model = App
    name = "create_app_auth_settings"
    permission_required = "api.create_app"

    def run(self, app_pk, user_pk, envs, disable_authentication, connections):
        user = self.get_user(pk=user_pk)
        if not user.has_perm(self.permission_required):
            # suggest send error to sentry with capture_messgae then mark complete so it
            # doesnt run again?
            return self.complete()

        app = self.get_object(pk=app_pk)
        if not user.github_api_token:
            # should a task that cannot be completed be marked as complete in DB?
            return self.complete()

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
    permission_required = "api.create_s3bucket"

    def run(self, bucket_pk, user_pk, bucket_owner="APP"):
        bucket = self.get_object(pk=bucket_pk)
        # this will already have run when the obj was created via modelform validation.
        # Is it unnecessary to call again?
        if cluster.S3Bucket(bucket).exists(bucket.name, bucket_owner=bucket_owner):
            # should a task that cannot be completed be marked as complete in DB?
            return self.complete()

        user = self.get_user(pk=user_pk)
        if not user.has_perm(self.permission_required):
            # suggest send error to sentry with capture_messgae then mark complete so it
            # doesnt run again?
            return self.complete()

        bucket.cluster.create(owner=bucket_owner)
        self.complete()


class CreateAppAWSRole(BaseTaskHandler):
    model = App
    name = "create_app_aws_role"
    permission_required = "api.create_app"

    def run(self, app_pk, user_pk):
        user = self.get_user(pk=user_pk)
        if not user.has_perm(self.permission_required):
            # suggest send error to sentry with capture_messgae then mark complete so it
            # doesnt run again?
            return self.complete()

        app = self.get_object(pk=app_pk)
        cluster.App(app).create_iam_role()
        self.complete()


class GrantAppS3BucketAccess(BaseTaskHandler):

    model = AppS3Bucket
    name = 'grant_app_s3bucket_access'
    permission_required = 'api.create_apps3bucket'

    def run(self, app_s3_bucket_pk, user_pk):
        user = self.get_user(pk=user_pk)
        if not user.has_perm(self.permission_required):
            # suggest send error to sentry with capture_messgae then mark complete so it
            # doesnt run again?
            return self.complete()

        app_bucket = self.get_object(pk=app_s3_bucket_pk)

        # TODO verify user?

        cluster.App(app_bucket.app).grant_bucket_access(
            app_bucket.s3bucket.arn,
            app_bucket.access_level,
            app_bucket.resources,
        )
        self.complete()


class GrantUserS3BucketAccess(BaseTaskHandler):

    model = UserS3Bucket
    name = "grant_user_s3bucket_access"
    permission_required = "api.create_users3bucket"

    def run(self, bucket_pk, user_pk):
        user = self.get_user(pk=user_pk)
        if not user.has_perm(self.permission_required):
            # suggest send error to sentry with capture_messgae then mark complete so it
            # doesnt run again?
            return self.complete()

        user_bucket = self.get_object(pk=bucket_pk)

        cluster.User(user_bucket.user).grant_bucket_access(
            user_bucket.s3bucket.arn,
            user_bucket.access_level,
            user_bucket.resources,
        )
        self.complete()


create_app_aws_role = celery_app.register_task(CreateAppAWSRole())
create_s3bucket = celery_app.register_task(CreateS3Bucket())
grant_app_s3bucket_access = celery_app.register_task(GrantAppS3BucketAccess())
grant_user_s3bucket_access = celery_app.register_task(GrantUserS3BucketAccess())
create_app_auth_settings = celery_app.register_task(CreateAppAuthSettings())
