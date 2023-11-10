# First-party/Local
from controlpanel.settings.common import *

ENV = "test"

AWS_DATA_ACCOUNT_ID = "123456789012"  # XXX DO NOT CHANGE - it will break moto tests

LOGGING["loggers"]["django_structlog"]["level"] = "WARNING"  # noqa: F405
LOGGING["loggers"]["controlpanel"]["level"] = "WARNING"  # noqa: F405

AUTHENTICATION_BACKENDS = [
    "rules.permissions.ObjectPermissionBackend",
    "django.contrib.auth.backends.ModelBackend",
]
MIDDLEWARE.remove("mozilla_django_oidc.middleware.SessionRefresh")  # noqa: F405
REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"].remove(  # noqa: F405
    "mozilla_django_oidc.contrib.drf.OIDCAuthentication",
)
OIDC_OP_JWKS_ENDPOINT = "https://example.com/.well-known/jwks.json"
OIDC_ALLOW_UNSECURED_JWT = True
OIDC_DOMAIN = "oidc.idp.example.com"

TOOLS_DOMAIN = "example.com"

CSRF_COOKIE_SECURE = False
SESSION_COOKIE_SECURE = False

SLACK = {
    "api_token": "test-slack-api-token",
    "channel": "test-slack-channel",
}

SQS_REGION = "eu-west-1"
USE_LOCAL_MESSAGE_BROKER = False
