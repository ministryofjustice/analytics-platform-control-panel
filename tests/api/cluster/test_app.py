from unittest.mock import MagicMock, patch

import pytest

from controlpanel.api import cluster, models


@pytest.fixture
def app():
    return models.App(slug="slug", repo_url="https://gitpub.example.com/test-repo")


@pytest.yield_fixture
def authz():
    with patch("controlpanel.api.cluster.auth0") as auth0:
        yield auth0.AuthorizationAPI.return_value


def test_app_create_iam_role(aws, app):
    cluster.App(app).create_iam_role()
    aws.create_app_role.assert_called_with(app)


def test_app_delete(aws, app, authz, helm):
    cluster.App(app).delete()

    aws.delete_role.assert_called_with(app.iam_role_name)
    authz.delete_group.assert_called_with(group_name=app.slug)
    helm.delete.assert_called_with(app.release_name)


def test_app_delete_eks(aws, app, authz, helm):
    with patch("controlpanel.api.aws.settings.EKS", True):
        cluster.App(app).delete()

    aws.delete_role.assert_called_with(app.iam_role_name)
    authz.delete_group.assert_called_with(group_name=app.slug)
    helm.delete_eks.assert_called_with(cluster.App.APPS_NS, app.release_name)


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
