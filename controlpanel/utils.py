import json
import re

from channels.exceptions import StopConsumer
from channels.generic.http import AsyncHttpConsumer
from django.template.defaultfilters import slugify


INVALID_CHARS = re.compile(r"[^-a-z0-9]")
SURROUNDING_HYPHENS = re.compile(r"^-*|-*$")


def github_repository_name(url):
    """
    Get the repository name from a Github URL
    """
    repo = url.rstrip("/")

    if repo.endswith(".git"):
        repo = repo[:-4]

    _, name = repo.rsplit("/", 1)

    return name


def is_truthy(value):
    return str(value).lower() not in ("", "n", "no", "off", "false", "0")


def s3_slugify(name):
    """
    Create a slug using standard Django slugify, but replace underscores with
    hyphens so that it's valid for S3
    """
    return re.sub(r"_+", "-", slugify(name))


def sanitize_dns_label(label):
    label = label.lower()

    # labels may contain only letters, digits and hyphens
    label = re.sub(r"[^a-z0-9]+", "-", label)

    # labels must start with an alphanumeric character
    label = re.sub(r"^[^a-z0-9]*", "", label)

    # labels must be max 63 chars
    label = label[:63]

    # labels must end with an alphanumeric character
    label = re.sub(r"[^a-z0-9]*$", "", label)

    return label


def sanitize_environment_variable(s):
    return name.upper().replace("-", "_")


def webapp_release_name(repo_name):
    name = repo_name.lower()
    name = SURROUNDING_HYPHENS.sub("", INVALID_CHARS.sub("-", name))
    return name[:50]


class PatchedAsyncHttpConsumer(AsyncHttpConsumer):
    """
    Patch AsyncHttpConsumer so that it doesn't disconnect immediately
    This should be removed when Django Channels is fixed
    See: https://github.com/django/channels/issues/1302
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.keepalive = False

    async def send_body(self, body, *, more_body=False):
        if more_body:
            self.keepalive = True
        assert isinstance(body, bytes), "Body is not bytes"
        await self.send(
            {"type": "http.response.body", "body": body, "more_body": more_body},
        )

    async def http_request(self, message):
        if "body" in message:
            self.body.append(message["body"])
        if not message.get('more_body'):
            try:
                await self.handle(b''.join(self.body))
            finally:
                if not self.keepalive:
                    await self.disconnect()
                    raise StopConsumer()

