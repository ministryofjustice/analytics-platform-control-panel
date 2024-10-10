# First-party/Local
from controlpanel.api.message_broker import MessageBrokerClient


def send_task(task):
    """
    Helper to send a task to the task queue
    """
    broker = MessageBrokerClient()
    broker.client.send_message(queue_name=task.queue_name, message_body=task.message_body)
