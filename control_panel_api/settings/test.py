from .base import *
from unittest.mock import MagicMock


ENV = 'test'
AWS_API_CLIENT_HANDLER = MagicMock()
BUCKET_REGION = 'eu-test-2'
LOGS_BUCKET_NAME = 'moj-test-logs'
IAM_ARN_BASE = 'arn:aws:iam::123'
K8S_WORKER_ROLE_NAME = 'test-k8s-worker-role'
SAML_PROVIDER = 'test'
SUBPROCESS_MODULE = MagicMock()
