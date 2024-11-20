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

OIDC_APP_EKS_PROVIDER = "oidc-app-example"

TOOLS_DOMAIN = "example.com"

CSRF_COOKIE_SECURE = False
SESSION_COOKIE_SECURE = False

SLACK = {
    "api_token": "test-slack-api-token",
    "channel": "test-slack-channel",
}

DPR_DATABASE_NAME = "test_database"
SQS_REGION = "eu-west-1"
USE_LOCAL_MESSAGE_BROKER = False

QUICKSIGHT_ACCOUNT_ID = "123456789012"
QUICKSIGHT_ACCOUNT_REGION = "eu-west-2"
QUICKSIGHT_DOMAINS = "http://localhost:8000"
QUICKSIGHT_ASSUMED_ROLE = "arn:aws:iam::123456789012:role/quicksight_test"

OIDC_CPANEL_API_AUDIENCE = "test-audience"
