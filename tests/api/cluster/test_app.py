# Standard library
from unittest.mock import MagicMock, patch

# Third-party
import pytest

# First-party/Local
from controlpanel.api import cluster, models
from controlpanel.api.cluster import BASE_ASSUME_ROLE_POLICY


@pytest.fixture
def app():
    return models.App(slug="slug", repo_url="https://gitpub.example.com/test-repo")


@pytest.yield_fixture
def aws_create_role():
    with patch(
        "controlpanel.api.cluster.AWSRole.create_role"
    ) as aws_create_role_action:
        yield aws_create_role_action


@pytest.yield_fixture
def aws_delete_role():
    with patch(
        "controlpanel.api.cluster.AWSRole.delete_role"
    ) as aws_delete_role_action:
        yield aws_delete_role_action


def test_app_create_iam_role(aws_create_role, app):
    cluster.App(app).create_iam_role()
    aws_create_role.assert_called_with(app.iam_role_name, BASE_ASSUME_ROLE_POLICY)


def test_app_delete(aws_delete_role, app):
    app.repo_url = "https://github.com/moj-analytical-services/my_repo"
    cluster.App(app).delete(github_api_token="testing")
    aws_delete_role.assert_called_with(app.iam_role_name)


mock_ingress = MagicMock(name="Ingress")
mock_ingress.spec.rules = [MagicMock(name="Rule", host="test-app.example.com")]
