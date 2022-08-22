from controlpanel.settings.common import *


ENV = 'test'

AWS_COMPUTE_ACCOUNT_ID = "test_compute_account_id"
AWS_DATA_ACCOUNT_ID = "123456789012"  # XXX DO NOT CHANGE - it will break moto tests
K8S_WORKER_ROLE_NAME = "nodes.example.com"
SAML_PROVIDER = "test-saml"

LOGGING["loggers"]["django_structlog"]["level"] = "WARNING"
LOGGING["loggers"]["controlpanel"]["level"] = "WARNING"

AUTHENTICATION_BACKENDS = [
    'rules.permissions.ObjectPermissionBackend',
    'django.contrib.auth.backends.ModelBackend',
]
MIDDLEWARE.remove('mozilla_django_oidc.middleware.SessionRefresh')
REST_FRAMEWORK['DEFAULT_AUTHENTICATION_CLASSES'].remove(
    'mozilla_django_oidc.contrib.drf.OIDCAuthentication',
)
OIDC_OP_JWKS_ENDPOINT = "https://example.com/.well-known/jwks.json"
OIDC_ALLOW_UNSECURED_JWT = True
OIDC_DOMAIN = "oidc.idp.example.com"

TOOLS_DOMAIN = 'example.com'

CSRF_COOKIE_SECURE = False
SESSION_COOKIE_SECURE = False

SLACK = {
    "api_token": "test-slack-api-token",
    "channel": "test-slack-channel",
}
