from unittest.mock import MagicMock

from django.conf import settings
import pytest

from controlpanel.api import cluster, models


@pytest.fixture
def app():
    return models.App(slug="slug", repo_url="https://gitpub.example.com/test-repo")


def test_app_create_iam_role(aws, app):
    cluster.App(app).create()
    aws.create_app_role.assert_called_with(app.iam_role_name)


def test_app_delete_iam_role(aws, app):
    cluster.App(app).delete()
    aws.delete_role.assert_called_with(app.iam_role_name)


mock_ingress = MagicMock(name="Ingress")
mock_ingress.spec.rules = [MagicMock(name="Rule", host="test-app.example.com")]


@pytest.mark.parametrize(
    "ingresses, expected_url",
    [
        ([], None),
        (["ingress_1", "ingress_2"], None),
        ([mock_ingress], "https://test-app.example.com"),
    ],
    ids=["no-ingresses", "multiple-ingresses", "single-ingress"],
)
def test_app_url(k8s_client, app, ingresses, expected_url):
    list_namespaced_ingress = k8s_client.ExtensionsV1beta1Api.list_namespaced_ingress

    list_namespaced_ingress.return_value.items = ingresses
    assert cluster.App(app).url == expected_url
    list_namespaced_ingress.assert_called_once_with(
        "apps-prod", label_selector="repo=test-repo"
    )
