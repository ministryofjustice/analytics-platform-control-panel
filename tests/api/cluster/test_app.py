from unittest.mock import MagicMock

import pytest

from controlpanel.api.cluster import BASE_ROLE_POLICY, App
from controlpanel.api import models

from django.conf import settings


@pytest.fixture
def app_model():
    return models.App(slug="slug", repo_url="https://gitpub.example.com/test-repo")


@pytest.fixture
def app(app_model):
    return App(app_model)


def test_app_iam_role_name(app, app_model):
    expected_iam_role_name = f"{settings.ENV}_app_{app_model.slug}"
    assert app.iam_role_name == expected_iam_role_name


def test_app_create_iam_role(aws, app):
    app.create_iam_role()

    aws.create_role.assert_called_with(app.iam_role_name, BASE_ROLE_POLICY)


def test_app_delete_iam_role(aws, app):
    app.delete_iam_role()
    aws.delete_role.assert_called_with(app.iam_role_name)


mock_ingress = MagicMock(name="Ingress")
mock_ingress.spec.rules = [MagicMock(name="Rule", host="test-app.example.com")]


@pytest.mark.parametrize(
    "ingresses, expected_url",
    [
        ([], None),
        (["ing_1", "ing_2"], None),
        ([mock_ingress], "https://test-app.example.com"),
    ],
    ids=["no-ingresses", "multiple-ingresses", "single-ingress"],
)
def test_app_url(k8s_client, app, app_model, ingresses, expected_url):
    list_namespaced_ingress = k8s_client.ExtensionsV1beta1Api.list_namespaced_ingress

    list_namespaced_ingress.return_value.items = ingresses
    assert app.url == expected_url
    list_namespaced_ingress.assert_called_once_with(
        "apps-prod", label_selector="repo=test-repo"
    )
