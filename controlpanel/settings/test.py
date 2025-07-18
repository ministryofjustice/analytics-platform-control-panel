# First-party/Local
from controlpanel.settings.common import *

ENV = "test"

AWS_DATA_ACCOUNT_ID = "123456789012"  # XXX DO NOT CHANGE - it will break moto tests

LOGGING["loggers"]["django_structlog"]["level"] = "WARNING"  # noqa: F405
LOGGING["loggers"]["controlpanel"]["level"] = "WARNING"  # noqa: F405

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
QUICKSIGHT_DOMAINS = ["http://localhost:8000"]
QUICKSIGHT_ASSUMED_ROLE = "arn:aws:iam::123456789012:role/quicksight_test"
IDENTITY_CENTER_ASSUMED_ROLE = "arn:aws:iam::123456789012:role/identity_center_test"
IDENTITY_CENTER_ACCOUNT_REGION = "eu-west-2"
QUICKSIGHT_READER_GROUP_NAME = "test-reader-group"
QUICKSIGHT_AUTHOR_GROUP_NAME = "test-author-group"
QUICKSIGHT_ADMIN_GROUP_NAME = "test-admin-group"
AZURE_HOLDING_GROUP_NAME = "test-holding-group"

OIDC_CPANEL_API_AUDIENCE = "test-audience"

FEEDBACK_BUCKET_NAME = "test-feedback-bucket"
DASHBOARD_SERVICE_URL = "http://test-dashboard-service-url/"
DASHBOARD_AUTH0_ROLE_ID = "rol_ab0CdEf1GHiJKlmN"  # gitleaks:allow

NOTIFY_API_KEY = "test-key"
NOTIFY_DASHBOARD_ACCESS_TEMPLATE_ID = "test-template-id"

PAGERDUTY_TOKEN = "test_token"
PAGERDUTY_WEBHOOK_SECRET = "example-webhook-secret"
