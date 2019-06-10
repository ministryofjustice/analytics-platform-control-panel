from controlpanel.settings.common import *


ENV = 'test'

K8S_WORKER_ROLE_NAME = "nodes.example.com"
SAML_PROVIDER = "test-saml"

LOGGING["loggers"]["django"]["level"] = "WARNING"

AUTHENTICATION_BACKENDS = ['django.contrib.auth.backends.ModelBackend']
MIDDLEWARE.remove('mozilla_django_oidc.middleware.SessionRefresh')
REST_FRAMEWORK['DEFAULT_AUTHENTICATION_CLASSES'].remove(
    'mozilla_django_oidc.contrib.drf.OIDCAuthentication',
)
OIDC_OP_JWKS_ENDPOINT = "https://example.com/.well-known/jwks.json"
OIDC_ALLOW_UNSECURED_JWT = True
OIDC_DOMAIN = "oidc.idp.example.com"

TOOLS_DOMAIN = 'example.com'
TOOLS["testtool"] = {
    "domain": "auth.example.com",
    "client_id": "42",
    "client_secret": "secret",
}
