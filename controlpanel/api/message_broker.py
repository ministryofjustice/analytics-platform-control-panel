# Standard library
import base64
import json
import os
import socket
import uuid
from collections.abc import Mapping

# First-party/Local
from controlpanel import celery_app
from controlpanel.api.aws import AWSSQS


class MessageProtocolError(Exception):
    pass


class MessageProtocol:

    def __init__(self, task_id: str, task_name: str, queue_name: str, args=None, kwargs=None):
        self.task_id = task_id
        self.task_name = task_name
        self.queue_name = queue_name
        self.args = args or ()
        self.kwargs = kwargs or {}
        self._validate()

    def _validate(self):
        if not isinstance(self.args, (list, tuple)):
            raise TypeError("task args must be a list or tuple")
        if not isinstance(self.kwargs, Mapping):
            raise TypeError("task keyword arguments must be a mapping")
        try:
            uuid.UUID(str(self.task_id))
        except ValueError:
            raise TypeError("task id arguments must be a uuid")
        if not self.task_name:
            raise TypeError("task name arguments must not be blank")
        if not self.queue_name:
            raise TypeError("queue name arguments must not be blank")

    def prepare_message(self):
        raise NotImplementedError("Note implemented")


class SimpleBase64:
    """Base64 codec."""

    @staticmethod
    def str_to_bytes(s):
        """Convert str to bytes."""
        if isinstance(s, str):
            return s.encode()
        return s

    @staticmethod
    def bytes_to_str(s):
        """Convert bytes to str."""
        if isinstance(s, bytes):
            return s.decode(errors="replace")
        return s

    def encode(self, s):
        return self.bytes_to_str(base64.b64encode(self.str_to_bytes(s)))

    def decode(self, s):
        return base64.b64decode(self.str_to_bytes(s))


class CeleryTaskMessage(MessageProtocol):

    #: Default body encoding.
    DEFAULT_BODY_ENCODING = "base64"
    DEFAULT_CONTENT_TYPE = "application/json"
    DEFAULT_CONTENT_ENCODING = "utf-8"
    DEFAULT_PRIORITY = 0

    DEFAULT_FUNC_SIGNATURE = None

    codecs = {"base64": SimpleBase64()}

    @staticmethod
    def _anon_nodename():
        """Return the nodename for this process (not a worker).

        This is used for e.g. the origin task message field.
        """
        return f"{os.getpid()}@{socket.gethostname()}"

    def _init_message(self):
        headers = {
            "lang": "py",
            "task": self.task_name,
            "id": self.task_id,
            "group": None,
            "root_id": self.task_id,
            "parent_id": None,
            "origin": self._anon_nodename(),
        }

        message = dict(
            headers=headers,
            properties={
                "correlation_id": self.task_id,
            },
            body=(
                self.args,
                self.kwargs,
                {
                    "callbacks": self.DEFAULT_FUNC_SIGNATURE,
                    "errbacks": self.DEFAULT_FUNC_SIGNATURE,
                    "chain": self.DEFAULT_FUNC_SIGNATURE,
                    "chord": self.DEFAULT_FUNC_SIGNATURE,
                },
            ),
        )
        return message

    def prepare_message(self):
        message = self._init_message()
        properties = message.get("properties") or {}
        info = properties.setdefault("delivery_info", {})
        info["priority"] = self.DEFAULT_PRIORITY or 0
        message["content-encoding"] = self.DEFAULT_CONTENT_ENCODING
        message["content-type"] = self.DEFAULT_CONTENT_TYPE
        message["body"], body_encoding = self.__class__.encode_body(
            json.dumps(message["body"]), self.DEFAULT_BODY_ENCODING
        )
        props = message["properties"]
        props.update(
            body_encoding=body_encoding,
            delivery_tag=str(uuid.uuid4()),
        )
        props["delivery_info"].update(
            routing_key=self.queue_name,
        )
        encoded_message, _ = self.__class__.encode_body(
            json.dumps(message), self.DEFAULT_BODY_ENCODING
        )
        return encoded_message

    @classmethod
    def encode_body(cls, body, encoding=None):
        if encoding:
            return cls.codecs.get(encoding).encode(body), encoding
        return body, encoding

    @classmethod
    def decode_body(cls, body, encoding=None):
        if encoding:
            return cls.codecs.get(encoding).decode(body)
        return body

    @classmethod
    def validate_message(cls, message):
        decoded_message = cls.decode_body(message, cls.DEFAULT_BODY_ENCODING)
        try:
            message_body = json.loads(decoded_message)
            assert message_body["content-encoding"] == cls.DEFAULT_CONTENT_ENCODING
            assert message_body["content-type"] == cls.DEFAULT_CONTENT_TYPE
            assert message_body["headers"]["id"] == message_body["headers"]["root_id"]
            assert message_body["headers"]["id"] == message_body["properties"]["correlation_id"]
            assert (
                type(json.loads(cls.decode_body(message_body["body"], cls.DEFAULT_BODY_ENCODING)))
                == list
            )
            return True, message_body
        except (ValueError, KeyError):
            return False, None


class MessageBrokerClient:
    DEFAULT_MESSAGE_PROTOCOL = "celery"

    MESSAGE_PROTOCOL_MAP_TABLE = {"celery": CeleryTaskMessage}

    def __init__(self, message_protocol=None):
        self.message_protocol = message_protocol or self.DEFAULT_MESSAGE_PROTOCOL
        self.client = self._get_client()

    def _get_client(self):
        return AWSSQS()

    def send_message(self, task_id, task_name, queue_name, args):
        message_class = self.MESSAGE_PROTOCOL_MAP_TABLE.get(self.message_protocol)
        if not message_class:
            raise MessageProtocolError("Not support!")

        message = message_class(
            task_id=task_id, task_name=task_name, queue_name=queue_name, args=tuple(args)
        ).prepare_message()
        self._get_client().send_message(queue_name=queue_name, message_body=message)
        return message


class LocalMessageBrokerClient:
    """
    Uses celery to send tasks so that it can be used with a message broker running
    locally such as Redis
    """

    @staticmethod
    def send_message(task_id, task_name, queue_name, args):
        return celery_app.send_task(
            task_name,
            task_id=task_id,
            queue_name=queue_name,
            args=args,
        )
