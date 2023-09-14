# Third-party
from celery import Task as CeleryTask

# First-party/Local
from controlpanel.api.models import Task, User


class BaseTaskHandler(CeleryTask):

    def complete(self):
        task = Task.objects.filter(task_id=self.request.id).first()
        if task:
            task.completed = True
            task.save()

    def run(self, *args, **kwargs):
        self.handle(*args, **kwargs)

    def handle(self, *args, **kwargs):
        """
        Should contain the logic to run the task, and will be called after the run
        method has been successfully called.
        """
        raise NotImplementedError("Task logic not implemented")


class BaseModelTaskHandler(BaseTaskHandler):
    name = None
    model = None
    object = None
    task_user_pk = None
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

    def run(self, obj_pk, task_user_pk, *args, **kwargs):
        """
        Default method that a celery Task object requires to be defined, and will be
        called by the worker when a message is received by the queue. This will look up
        the instance of the model, and store the PK of the user running the task to use
        to look up the user later if required. The `handle` method is then called
        with any other args and kwargs sent.
        """
        self.object = self.get_object(obj_pk)
        self.task_user_pk = task_user_pk
        self.handle(*args, **kwargs)
