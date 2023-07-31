import uuid
from django.conf import settings

from controlpanel.api.message_broker import MessageBrokerClient
from controlpanel.api.models.task import Task


class TaskError(Exception):
    pass


class TaskBase:

    QUEUE_NAME = settings.DEFAULT_QUEUE
    ENTITY_CLASS = None

    def __init__(self, entity, user=None, extra_data=None):
        self._message_broker_client = None
        self.entity = entity
        self.user = user
        self.extra_data = extra_data
        self._validate()

    def _validate(self):
        if not self.entity:
            raise TaskError("Please provide entity instance")
        if self.user and self.user.__class__.__name__ != "User":
            raise TaskError("The instance has to be user class")
        if self.entity.__class__.__name__ != self.ENTITY_CLASS:
            raise TaskError(f"The instance has to be {self.ENTITY_CLASS} class")

    @property
    def task_id(self):
        return str(uuid.uuid4())

    @property
    def task_description(self):
        raise NotImplementedError("Not implemented")

    @property
    def task_name(self):
        raise NotImplementedError("Not implemented")

    @property
    def message_broker_client(self):
        if self._message_broker_client is None:
            self._message_broker_client = MessageBrokerClient()
        return self._message_broker_client

    def _get_args_list(self):
        args = [self.entity.id]
        if self.user:
            args.append(self.user.id)
        return args

    def create_task(self):
        task_id = self.task_id
        message = self.message_broker_client.send_message(
            task_id=task_id,
            task_name=self.task_name,
            queue_name=self.QUEUE_NAME,
            args=self._get_args_list()
        )
        Task.objects.create(
            entity_class=self.ENTITY_CLASS,
            entity_description=self.entity.name,
            entity_id=self.entity.id,
            user_id=self.user.auth0_id if self.user else 'None',
            task_id=task_id,
            task_description=self.task_description,
            task_name=self.task_name,
            queue_name=self.QUEUE_NAME,
            message_body=message
        )
