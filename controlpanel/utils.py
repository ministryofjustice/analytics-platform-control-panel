# Standard library
import os
import re

# Third-party
import structlog
import yaml
from channels.exceptions import StopConsumer
from channels.generic.http import AsyncHttpConsumer
from django.conf import settings
from django.template.defaultfilters import slugify

log = structlog.getLogger(__name__)


INVALID_CHARS = re.compile(r"[^-a-z0-9]")
SURROUNDING_HYPHENS = re.compile(r"^-*|-*$")

_ENV_PREFIX_ = "_HOST"
_ENV_DEFAULT_ = "_DEFAULT"
_DEFAULT_APP_CONFIG_FILE_ = "./settings.yaml"


def github_repository_name(url):
    """
    Get the repository name from a Github URL
    """
    repo = url.rstrip("/")

    if repo.endswith(".git"):
        repo = repo[:-4]

    _, name = repo.rsplit("/", 1)

    return name


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
        if not message.get("more_body"):
            try:
                await self.handle(b"".join(self.body))
            finally:
                if not self.keepalive:
                    await self.disconnect()
                    raise StopConsumer()


class FeatureFlag:
    def __init__(self, enabled=False):
        self.enabled = enabled


class FeatureSet:
    """
    enabled_features:
      <feature flag>:
        Local: true
        Host-dev: true
        Host-prod: false
    """

    def __init__(self, feature_set_json, current_env):
        self._load_flags(feature_set_json, current_env)

    def _load_flags(self, feature_set_json, current_env):
        for feature_flag, feature_settings in feature_set_json.items():
            enabled = False
            if feature_settings.get(_ENV_DEFAULT_) is not None:
                enabled = feature_settings.get(_ENV_DEFAULT_)
            if (
                feature_settings.get("{}_{}".format(_ENV_PREFIX_, current_env))
                is not None
            ):
                enabled = feature_settings.get(
                    "{}_{}".format(_ENV_PREFIX_, current_env)
                )
            setattr(self, feature_flag, FeatureFlag(enabled))


class SettingLoader:
    """This function is to load the settings from yaml file,
    then will add those keys as variables into the global setting object
    it will check whether a key has existed in the setting file or not,
    if not, then it will load the value for this key from yaml file.
    Tf the value has been defined in the settings and has been defined in env var,
    then the env var take higher priority

    Each conf key can be different value under different ENV, e.g.
    node_name:
        _DEFAULT: test
        _HOST-local: test1
        _HOST-dev: test2
        _HOST-prod: test3
        _HOST-alpha: test4
    """

    def __init__(self, settings_in_json):
        self.settings_in_json = settings_in_json
        self._import_conf_into_settings()

    def _has_env_related_value(self, original_value, current_env):
        return (type(original_value) is dict) and (
            original_value.get(_ENV_DEFAULT_) is not None
            or original_value.get("{}_{}".format(_ENV_PREFIX_, current_env)) is not None
        )

    def _decide_value_for_key(self, setting_key, original_value):
        actual_value = original_value
        current_env = settings.ENV
        if setting_key in os.environ:
            actual_value = os.environ.get(setting_key)
        else:
            if self._has_env_related_value(original_value, current_env):
                if (
                    original_value.get("{}_{}".format(_ENV_PREFIX_, current_env))
                    is not None
                ):
                    actual_value = original_value.get(
                        "{}_{}".format(_ENV_PREFIX_, current_env)
                    )
                else:
                    actual_value = original_value.get(_ENV_DEFAULT_)
        return actual_value

    def _setup_feature_flags(self, feature_flags):
        setattr(settings, "features", FeatureSet(feature_flags, settings.ENV))

    def _import_conf_into_settings(self):
        if not self.settings_in_json:
            return

        for key, value in self.settings_in_json.items():
            if not hasattr(settings, key):
                if key.lower() == "enabled_features":
                    self._setup_feature_flags(value)
                else:
                    setattr(settings, key, self._decide_value_for_key(key, value))


def load_app_conf_from_file(yaml_file=None):
    yaml_file = yaml_file or _DEFAULT_APP_CONFIG_FILE_
    if not os.path.exists(yaml_file):
        log.error("Couldn't find the file {}".format(yaml_file))
        return
    try:
        with open(yaml_file, "r") as stream:
            yaml_settings = yaml.safe_load(stream)
        SettingLoader(yaml_settings)
    except AttributeError as ex:
        log.error("Failed to load the {} due to error ({})".format(yaml_file, str(ex)))
    except ValueError as ex1:
        log.error("Failed to load the {} due to error ({})".format(yaml_file, str(ex1)))
