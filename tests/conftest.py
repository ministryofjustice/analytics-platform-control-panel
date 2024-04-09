# Standard library
import uuid
from unittest.mock import mock_open, patch

# Third-party
import pytest
import yaml
from model_bakery import baker

# First-party/Local
from controlpanel.api import auth0
from controlpanel.utils import load_app_conf_from_file
from tests.api.fixtures.aws import *
from tests.api.fixtures.helm_mojanalytics_index import HELM_MOJANALYTICS_INDEX


@pytest.fixture()
def ExtendedAuth0():
    with patch(
        "auth0.authentication.GetToken.client_credentials"
    ) as client_credentials:
        client_credentials.return_value = {"access_token": "access_token_testing"}
        yield auth0.ExtendedAuth0()


@pytest.fixture
def fixture_get_group_id(ExtendedAuth0):
    with patch.object(ExtendedAuth0.groups, "get_group_id") as request:
        request.return_value = uuid.uuid4()
        yield request


def pytest_configure(config):
    load_app_conf_from_file()


@pytest.fixture()
def client(client):
    """A Django test client instance."""
    load_app_conf_from_file()
    return client


@pytest.fixture(autouse=True)
def k8s_client():
    """
    Mock calls to kubernetes
    """
    with patch("controlpanel.api.cluster.KubernetesClient") as k8s_client:
        yield k8s_client.return_value


@pytest.fixture(autouse=True)
def elasticsearch():
    """
    Mock calls to Elasticsearch
    """
    with patch("controlpanel.api.elasticsearch.Elasticsearch") as es, patch(
        "elasticsearch_dsl.search.scan"
    ):
        yield es.return_value


@pytest.fixture(autouse=True)
def helm():
    """
    Mock calls to Helm
    """
    with patch("controlpanel.api.cluster.helm") as helm:
        yield helm


@pytest.fixture
def helm_repository_index(autouse=True):
    """
    Mock the helm repository with some data
    """
    content = yaml.dump(HELM_MOJANALYTICS_INDEX)
    return mock_open(read_data=content)


@pytest.fixture(autouse=True)
def slack_WebClient():
    """
    Mock calls to Slack
    """
    with patch("controlpanel.api.slack.slack.WebClient") as WebClient:
        yield WebClient


@pytest.fixture
def superuser(
    db, slack_WebClient, iam, managed_policy, airflow_dev_policy, airflow_prod_policy
):
    return baker.make(
        "api.User",
        auth0_id="github|user_1",
        is_superuser=True,
        username="alice",
    )


@pytest.fixture
def users(db, superuser, iam, managed_policy, airflow_dev_policy, airflow_prod_policy):
    return {
        "superuser": superuser,
        "normal_user": baker.make(
            "api.User",
            auth0_id="github|user_2",
            username="bob",
            is_superuser=False,
        ),
        "other_user": baker.make(
            "api.User",
            username="carol",
            auth0_id="github|user_3",
        ),
    }


class Helpers:

    @staticmethod
    def validate_task_with_sqs_messages(
        messages, entity_class, entity_id, queue_name=settings.DEFAULT_QUEUE,
    ):
        from controlpanel.api.models import Task
        tasks_created = Task.objects.filter(
            entity_class=entity_class, entity_id=entity_id, queue_name=queue_name
        )
        found_tasks_cnt = 0
        tasks_cnt = 0
        for task in tasks_created:
            tasks_cnt += 1
            for message in messages:
                print(tasks_cnt, task.task_id, message["headers"]["id"])
                if str(task.task_id) == message["headers"]["id"]:
                    found_tasks_cnt += 1
                    assert message["headers"]["task"] == task.task_name
        assert len(message) > 0
        assert tasks_cnt > 0
        assert tasks_cnt == found_tasks_cnt

    @staticmethod
    def retrieve_messages(sqs, queue_name=settings.DEFAULT_QUEUE):
        from controlpanel.api.message_broker import CeleryTaskMessage
        queue = sqs.get_queue_by_name(QueueName=queue_name)
        messages = queue.receive_messages(
                MessageAttributeNames=['All'],
                MaxNumberOfMessages=10
            )
        decoded_messages = []
        for message in messages:
            valid, message_body = CeleryTaskMessage.validate_message(message.body)
            assert valid
            decoded_messages.append(message_body)
        return decoded_messages


@pytest.fixture
def helpers():
    return Helpers
