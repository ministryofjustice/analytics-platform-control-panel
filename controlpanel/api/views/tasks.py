# Third-party
from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from controlpanel.api.models import Task
from controlpanel.api.message_broker import MessageBrokerClient


class TaskAPIView(GenericAPIView):

    http_method_names = ["post"]
    permission_classes = (IsAuthenticated,)

    def _send_message(self, task_id):
        task = Task.objects.filter(task_id=task_id).first()
        if task:
            message_client = MessageBrokerClient()
            message_client.client.send_message(
                queue_name=task.queue_name,
                message_body=task.message_body
            )

    def post(self, request, *args, **kwargs):
        task_id = self.kwargs["task_id"]
        task_action = self.kwargs["action"]
        task_action_function = getattr(self, f"_{task_action}", None)
        if task_action_function and callable(task_action_function):
            task_action_function(task_id)
            return Response(status=status.HTTP_200_OK)
        else:
            return Response(status=status.HTTP_400_BAD_REQUEST)
