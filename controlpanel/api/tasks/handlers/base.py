# Third-party
from celery import Task as CeleryTask

# First-party/Local
from controlpanel.api.models import Task, User


class BaseModelTaskHandler(CeleryTask):
    name = None
    model = None
    permission_required = None
    object = None
    user = None
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
        except User.DoesNotExist:
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
        Default method that a celery Task object requires to be defined, and will be
        called by the worker when a message is received by the queue. This will look up
        and store the user and instance of the model, and validate the user can run the
        task for the instance. If these lookups and validation passes, the `handle`
        method is called, with any other args and kwargs sent.
        The handle method be defined on any subclass of BaseModelTaskHandler.
        """
        self.user = self.get_user(user_pk)
        if not self.user:
            return self.complete()

        self.object = self.get_object(obj_pk)
        if not self.has_permission(self.user, self.object):
            return self.complete()

        self.handle(*args, **kwargs)

    def handle(self, *args, **kwargs):
        """
        Should contain the logic to run the task, and will be called after the run
        method has been successfully called.
        """
        raise NotImplementedError("Task logic not implemented")
