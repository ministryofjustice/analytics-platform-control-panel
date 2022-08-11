from unittest.mock import mock_open, patch

from model_mommy import mommy
import yaml
import pytest

from controlpanel.utils import load_app_conf_from_file

from tests.api.fixtures.helm_mojanalytics_index import HELM_MOJANALYTICS_INDEX
from tests.api.fixtures.aws import *



def pytest_configure(config):
    load_app_conf_from_file()


@pytest.fixture()
def client(client):
    """A Django test client instance."""
    load_app_conf_from_file()
    return client


@pytest.yield_fixture(autouse=True)
def k8s_client():
    """
    Mock calls to kubernetes
    """
    with patch('controlpanel.api.cluster.KubernetesClient') as k8s_client:
        yield k8s_client.return_value


@pytest.yield_fixture(autouse=True)
def elasticsearch():
    """
    Mock calls to Elasticsearch
    """
    with patch('controlpanel.api.elasticsearch.Elasticsearch') as es, patch('elasticsearch_dsl.search.scan') as scan:
        yield es.return_value


@pytest.yield_fixture(autouse=True)
def github():
    """
    Mock calls to Github
    """
    with patch('controlpanel.api.github.Github') as Github:
        yield Github.return_value


@pytest.yield_fixture(autouse=True)
def helm():
    """
    Mock calls to Helm
    """
    with patch('controlpanel.api.cluster.helm') as helm:
        yield helm


@pytest.fixture
def helm_repository_index(autouse=True):
    """
    Mock the helm repository with some data
    """
    content = yaml.dump(HELM_MOJANALYTICS_INDEX)
    return mock_open(read_data=content)


@pytest.yield_fixture(autouse=True)
def slack_WebClient():
    """
    Mock calls to Slack
    """
    with patch('controlpanel.api.slack.slack.WebClient') as WebClient:
        yield WebClient


@pytest.fixture
def superuser(db, slack_WebClient, iam, managed_policy, airflow_dev_policy, airflow_prod_policy):
    return mommy.make(
        'api.User',
        auth0_id='github|user_1',
        is_superuser=True,
        username='alice',
    )


@pytest.fixture
def users(db, superuser, iam, managed_policy, airflow_dev_policy, airflow_prod_policy):
    return {
        'superuser': superuser,
        'normal_user': mommy.make(
            'api.User',
            auth0_id='github|user_2',
            username="bob",
            is_superuser=False,
        ),
        "other_user": mommy.make(
            "api.User",
            username="carol",
            auth0_id="github|user_3",
        ),
    }
