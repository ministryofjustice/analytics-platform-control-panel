from .base import *


ENV = 'test'
BUCKET_REGION = 'eu-test-2'
LOGS_BUCKET_NAME = 'moj-test-logs'
IAM_ARN_BASE = 'arn:aws:iam::123'
K8S_WORKER_ROLE_NAME = 'test-k8s-worker-role'
SAML_PROVIDER = 'test'
OIDC_DOMAIN = 'auth.example.com'

LOGGING['handlers']['console']['level'] = 'CRITICAL'
