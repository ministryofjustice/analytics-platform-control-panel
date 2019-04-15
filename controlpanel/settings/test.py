from controlpanel.settings.common import *


ENV = 'test'

IAM_ARN_BASE = "arn:test:iam::12345678"
K8S_WORKER_ROLE_NAME = "nodes.example.com"
SAML_PROVIDER = "test-saml"

LOGGING["loggers"]["django"]["level"] = "WARNING"

AUTHENTICATION_BACKENDS = ['django.contrib.auth.backends.ModelBackend']
MIDDLEWARE.remove('mozilla_django_oidc.middleware.SessionRefresh')
REST_FRAMEWORK['DEFAULT_AUTHENTICATION_CLASSES'].remove(
    'mozilla_django_oidc.contrib.drf.OIDCAuthentication',
)

TOOLS_DOMAIN = 'example.com'
TOOLS["testtool"] = {
    "domain": "auth.example.com",
    "client_id": "42",
    "client_secret": "secret",
}
