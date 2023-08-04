from celery import Task as CeleryTask

from controlpanel import celery_app
from controlpanel.api import cluster
from controlpanel.api.models import App, User, S3Bucket, UserS3Bucket, AppS3Bucket, Task


class BaseModelTaskHandler(CeleryTask):
    name = None
    model = None
    permission_required = None

    # can be applied to project settings also
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
        """
        Try to find the user, then check they have the correct permission required to
        run the task action.
        """
        try:
            return User.objects.get(pk=pk)
        except User.DoesNotExist as exc:
            # if the user is found, this should be a hard fail? So suggest log the error
            # and then mark as complete to stop task being rerun?
            return None

    def has_permission(self, user, obj=None):
        """
        Check that the user has permission to run the task on the given object.
        Override on the subclass for further permission checks.
        """
        if not self.permission_required:
            raise NotImplementedError("Must define a permission to check")

        if not user.has_perm(self.permission_required, obj=obj):
            # log that the user did not have permission?
            return False

        return True

    def complete(self):
        task = Task.objects.filter(task_id=self.request.id).first()
        if task:
            task.completed = True
            task.save()

    def run(self, obj_pk, user_pk, *args, **kwargs):
        """
        Default message that a celery Task object requires to be defined, and will be
        called by the worker when a message is received by the queue. This runs some
        lookups and validates the user, and if these pass calls `run_task` which must
        be defined on any subclass of BaseTaskHandler.
        """
        obj = self.get_object(obj_pk)
        user = self.get_user(user_pk)
        if not user:
            return self.complete()

        if not self.has_permission(user, obj):
            return self.complete()

        self.run_task(obj, user, *args, **kwargs)

    def run_task(self, *args, **kwargs):
        """
        Should contain the logic to run the task, and will be called after the run
        method has been successfully called.
        """
        raise NotImplementedError("Task logic not implemented")


class CreateAppAuthSettings(BaseModelTaskHandler):
    model = App
    name = "create_app_auth_settings"
    permission_required = "api.create_app"

    def has_permission(self, user, obj=None):
        if not user.github_api_token:
            return False
        return super().has_permission(user, obj)

    def run_task(self, app, user, envs, disable_authentication, connections):
        for env in envs:
            cluster.App(app, user.github_api_token).create_auth_settings(
                env_name=env,
                disable_authentication=disable_authentication,
                connections=connections,
            )
        self.complete()


class CreateS3Bucket(BaseModelTaskHandler):
    model = S3Bucket
    name = "create_s3bucket"
    permission_required = "api.create_s3bucket"

    def run_task(self, bucket, user, bucket_owner="APP"):
        bucket.cluster.create(owner=bucket_owner)
        self.complete()


class CreateAppAWSRole(BaseModelTaskHandler):
    model = App
    name = "create_app_aws_role"
    permission_required = "api.create_app"

    def run_task(self, app, user):
        cluster.App(app).create_iam_role()
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
