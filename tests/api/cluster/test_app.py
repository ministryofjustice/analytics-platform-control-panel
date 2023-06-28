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


@pytest.fixture
def aws_create_role():
    with patch(
        "controlpanel.api.cluster.AWSRole.create_role"
    ) as aws_create_role_action:
        yield aws_create_role_action


@pytest.fixture
def aws_delete_role():
    with patch(
        "controlpanel.api.cluster.AWSRole.delete_role"
    ) as aws_delete_role_action:
        yield aws_delete_role_action


@pytest.fixture(autouse=True)
def githubapi():
    """
    Mock calls to Github
    """
    with patch("controlpanel.api.cluster.GithubAPI") as GithubAPI:
        yield GithubAPI.return_value


@pytest.fixture(autouse=True)
def repos(githubapi):
    test_repo = {
        "full_name": "Test App",
        "html_url": "https://github.com/moj-analytical-services/test_app",
    }
    githubapi.get_repository.return_value = test_repo
    githubapi.get_repo_envs.return_value = ["test"]
    yield githubapi


def test_app_create_iam_role(aws_create_role, app):
    cluster.App(app).create_iam_role()
    aws_create_role.assert_called_with(app.iam_role_name, BASE_ASSUME_ROLE_POLICY)


@pytest.fixture  # noqa: F405
def authz():
    with patch("controlpanel.api.auth0.ExtendedAuth0") as authz:
        yield authz()


def test_app_delete(aws_delete_role, app, authz):
    app.repo_url = "https://github.com/moj-analytical-services/my_repo"
    cluster.App(app, github_api_token="testing").delete()
    aws_delete_role.assert_called_with(app.iam_role_name)


mock_ingress = MagicMock(name="Ingress")
mock_ingress.spec.rules = [MagicMock(name="Rule", host="test-app.example.com")]
