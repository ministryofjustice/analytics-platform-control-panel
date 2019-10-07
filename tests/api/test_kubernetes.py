from unittest.mock import patch

import kubernetes
import pytest

from controlpanel.api.kubernetes import KubernetesClient



SERVICE_ACCOUNT_TEST_TOKEN = "test-service-account-token"



@pytest.yield_fixture()
def k8s_config():
    config = kubernetes.client.Configuration()
    with patch("controlpanel.api.kubernetes.kubernetes.client.Configuration") as Configuration:
        config.host = "https://api.k8s.localhost"
        config.api_key_prefix = {"authorization": "Bearer"}
        config.api_key = {"authorization": SERVICE_ACCOUNT_TEST_TOKEN}
        Configuration.return_value = config
        yield Configuration


def test_kubernetes_client_constructor_when_no_creds_passed():
    with pytest.raises(ValueError):
        KubernetesClient()


def test_kubernetes_client_constructor_when_use_cpanel_creds_and_id_token_passed():
    with pytest.raises(ValueError):
        KubernetesClient(id_token="test-token", use_cpanel_creds=True)


def test_kubernetes_client_constructor_when_id_token_passed(k8s_config):
    id_token = "test-user-id-token"

    client = KubernetesClient(id_token=id_token)

    config = client.api_client.configuration
    assert config.api_key_prefix["authorization"] == "Bearer"
    assert config.api_key["authorization"] == id_token


def test_kubernetes_client_constructor_when_use_cpanel_creds_true(k8s_config):
    client = KubernetesClient(use_cpanel_creds=True)

    config = client.api_client.configuration

    assert config.api_key_prefix["authorization"] == "Bearer"
    assert config.api_key["authorization"] == SERVICE_ACCOUNT_TEST_TOKEN

