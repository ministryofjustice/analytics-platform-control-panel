# Standard library
from copy import deepcopy
from unittest.mock import MagicMock, call, patch

# Third-party
import pytest
import requests

# First-party/Local
from controlpanel.api import cluster, models
from controlpanel.api.cluster import BASE_ASSUME_ROLE_POLICY
from controlpanel.api.github import RepositoryNotFound


@pytest.fixture
def app():
    return models.App(
        slug="test-app",
        repo_url="https://gitpub.example.com/test-repo",
        namespace="test-namespace",
    )


@pytest.fixture
def aws_create_role():
    with patch("controlpanel.api.cluster.AWSRole.create_role") as aws_create_role_action:
        yield aws_create_role_action


@pytest.fixture
def aws_delete_role():
    with patch("controlpanel.api.cluster.AWSRole.delete_role") as aws_delete_role_action:
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


@pytest.fixture
def oidc_provider_statement(app, settings):
    statement = dict()
    statement["Sid"] = "AllowCloudPlatformOIDCProvider"
    statement["Effect"] = "Allow"
    statement["Action"] = "sts:AssumeRoleWithWebIdentity"
    statement["Principal"] = {
        "Federated": f"arn:aws:iam::{settings.AWS_DATA_ACCOUNT_ID}:oidc-provider/{settings.OIDC_APP_EKS_PROVIDER}"  # noqa
    }
    statement["Condition"] = {
        "StringEquals": {
            f"{settings.OIDC_APP_EKS_PROVIDER}:aud": "sts.amazonaws.com",
            f"{settings.OIDC_APP_EKS_PROVIDER}:sub": [
                f"system:serviceaccount:{app.namespace}-dev:{app.namespace}-dev-sa",  # noqa
                f"system:serviceaccount:{app.namespace}-prod:{app.namespace}-prod-sa",  # noqa
            ],
        }
    }
    return statement


def test_oidc_provider_statement(app, oidc_provider_statement):
    assert cluster.App(app).oidc_provider_statement == oidc_provider_statement


@patch("controlpanel.api.cluster.App.get_deployment_envs")
@patch("controlpanel.api.cluster.App._create_secrets")
def test_app_create_iam_role(
    _create_secrets, get_deployment_envs, aws_create_role, app, oidc_provider_statement
):
    expected_assume_role = deepcopy(BASE_ASSUME_ROLE_POLICY)
    expected_assume_role["Statement"].append(oidc_provider_statement)

    get_deployment_envs.return_value = ["dev", "prod"]
    cluster.App(app).create_iam_role()

    aws_create_role.assert_called_with(app.iam_role_name, expected_assume_role)
    _create_secrets.assert_has_calls(
        [
            call(env_name="dev"),
            call(env_name="prod"),
        ]
    )


@pytest.fixture  # noqa: F405
def authz():
    with patch("controlpanel.api.auth0.ExtendedAuth0") as authz:
        yield authz()


def test_app_delete(aws_delete_role, app, authz):
    app.repo_url = "https://github.com/moj-analytical-services/my_repo"
    cluster.App(app, github_api_token="testing").delete()
    aws_delete_role.assert_called_with(app.iam_role_name)


@pytest.fixture
def ExtendedAuth0():
    with patch("controlpanel.api.auth0.ExtendedAuth0") as authz:
        authz.DEFAULT_CONNECTION_OPTION = "email"
        yield authz.return_value


def test_update_auth_connections(app, ExtendedAuth0):
    with (
        patch.object(ExtendedAuth0, "get_client_enabled_connections") as get_conns,
        patch.object(ExtendedAuth0, "update_client_auth_connections") as update_conns,
        patch("controlpanel.api.cluster.App.create_or_update_env_var") as create_or_update,
    ):
        testing_env = "testing_env"
        testing_client_id = "testing_client_id"
        app.app_conf = {
            models.App.KEY_WORD_FOR_AUTH_SETTINGS: {testing_env: {"client_id": testing_client_id}}
        }
        app.repo_url = "https://github.com/moj-analytical-services/my_repo"

        # Change to use non-passwordless connection
        new_conns = ({"github": {}},)
        get_conns.return_value = {testing_client_id: "email"}
        cluster.App(app, github_api_token="testing").update_auth_connections(
            testing_env, new_conns=new_conns
        )
        create_or_update.assert_called_with(
            env_name="testing_env", key_name="AUTH0_PASSWORDLESS", key_value=False
        )
        update_conns.assert_called_with(
            app_name=f"data-platform-app-{app.slug}-testing_env",
            client_id="testing_client_id",
            new_conns=new_conns,
            existing_conns="email",
        )

        # Change to use passwordless connection
        new_conns = {"email": {}}
        get_conns.return_value = {testing_client_id: "github"}
        cluster.App(app, github_api_token="testing").update_auth_connections(
            testing_env, new_conns=new_conns
        )
        create_or_update.assert_called_with(
            env_name="testing_env", key_name="AUTH0_PASSWORDLESS", key_value=True
        )
        update_conns.assert_called_with(
            app_name=f"data-platform-app-{app.slug}-testing_env",
            client_id="testing_client_id",
            new_conns=new_conns,
            existing_conns="github",
        )


@patch("controlpanel.api.models.App.env_allowed_ip_ranges", new=MagicMock(return_value="1.2.3"))
def test_create_secrets(app):
    app_cluster = cluster.App(app)
    secrets = {
        app_cluster.IP_RANGES: "1.2.3",
        app_cluster.APP_ROLE_ARN: app.iam_role_arn,
    }
    with patch.object(app_cluster, "create_or_update_secrets"):
        app_cluster._create_secrets(env_name="dev", client=None)
        app_cluster.create_or_update_secrets.assert_called_once_with(
            env_name="dev", secret_data=secrets
        )


@pytest.mark.parametrize(
    "key, expected",
    [
        ("AUTH0_CLIENT_ID", "AUTH0_CLIENT_ID"),
        ("AUTH0_CLIENT_SECRET", "AUTH0_CLIENT_SECRET"),
        ("AUTH0_DOMAIN", "AUTH0_DOMAIN"),
        ("AUTH0_PASSWORDLESS", "AUTH0_PASSWORDLESS"),
        ("APP_ROLE_ARN", "APP_ROLE_ARN"),
        ("CUSTOM_SETTING", "XXX_CUSTOM_SETTING"),
    ],
)
def test_format_github_key_name(key, expected):
    assert cluster.App(None).format_github_key_name(key_name=key) == expected


@pytest.mark.parametrize(
    "key, expected",
    [
        ("AUTH0_CLIENT_ID", "AUTH0_CLIENT_ID"),
        ("AUTH0_CLIENT_SECRET", "AUTH0_CLIENT_SECRET"),
        ("AUTH0_DOMAIN", "AUTH0_DOMAIN"),
        ("AUTH0_PASSWORDLESS", "AUTH0_PASSWORDLESS"),
        ("APP_ROLE_ARN", "APP_ROLE_ARN"),
        ("XXX_CUSTOM_SETTING", "CUSTOM_SETTING"),
        ("XXX_XXX_CUSTOM_SETTING", "XXX_CUSTOM_SETTING"),
    ],
)
def test_get_github_key_display_name(key, expected):
    assert cluster.App(None).get_github_key_display_name(key) == expected


@patch("controlpanel.api.cluster.App.remove_auth_settings")
@patch("controlpanel.api.cluster.App.get_deployment_envs")
def test_delete_http_error(get_deployment_envs_mock, remove_auth_settings_mock, app):
    app_cluster = cluster.App(app, github_api_token="testing")
    get_deployment_envs_mock.side_effect = requests.exceptions.HTTPError()

    app_cluster.delete()
    assert remove_auth_settings_mock.call_count == 2


@patch("controlpanel.api.cluster.App._get_auth0_instance")
@patch("controlpanel.api.cluster.App.delete_env_var")
@patch("controlpanel.api.cluster.App.delete_secret")
def test_remove_auth_settings_repo_error(
    delete_secret_mock, delete_env_var_mock, get_auth0_mock, app
):
    auth0_instance = MagicMock()
    app_cluster = cluster.App(app)
    delete_secret_mock.side_effect = RepositoryNotFound("test")
    get_auth0_mock.return_value = auth0_instance

    app_cluster.remove_auth_settings(env_name="dev")
    delete_secret_mock.assert_called_once()
    delete_env_var_mock.assert_not_called()
    auth0_instance.clear_up_app.assert_called_once()


# TODO can this be removed?
mock_ingress = MagicMock(name="Ingress")
mock_ingress.spec.rules = [MagicMock(name="Rule", host="test-app.example.com")]
