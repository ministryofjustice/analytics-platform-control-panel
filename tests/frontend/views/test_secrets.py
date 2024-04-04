# Standard library
from unittest.mock import patch

# Third-party
from django.urls import reverse
from model_mommy import mommy

# First-party/Local
from tests.api.fixtures.aws import *

NUM_APPS = 3


@pytest.fixture(autouse=True)  # noqa: F405
def enable_db_for_all_tests(db):
    pass


@pytest.fixture(autouse=True)  # noqa: F405
def github_api_token():
    with patch("controlpanel.api.models.user.auth0.ExtendedAuth0") as ExtendedAuth0:
        ExtendedAuth0.return_value.users.get.return_value = {
            "identities": [
                {
                    "provider": "github",
                    "access_token": "dummy-access-token",
                },
            ],
        }
        yield ExtendedAuth0.return_value


@pytest.fixture(autouse=True)  # noqa: F405
def users(users):
    users.update(
        {
            "app_admin": mommy.make("api.User", username="app_admin"),
        }
    )
    return users


@pytest.fixture(autouse=True)  # noqa: F405
def app(users):
    mommy.make("api.App", NUM_APPS - 1)
    app = mommy.make("api.App")
    mommy.make("api.UserApp", user=users["app_admin"], app=app, is_admin=True)
    return app


@pytest.fixture(autouse=True)
def githubapi():
    """
    Mock calls to Github
    """
    with patch("controlpanel.frontend.forms.GithubAPI"), \
            patch("controlpanel.api.cluster.GithubAPI") as GithubAPI:
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


@pytest.fixture(autouse=True)  # noqa: F405
def s3buckets(app):
    with patch("controlpanel.api.aws.AWSBucket.create"):
        buckets = {
            "not_connected": mommy.make("api.S3Bucket"),
            "connected": mommy.make("api.S3Bucket"),
        }
        return buckets


@pytest.fixture  # noqa: F405
def apps3bucket(app, s3buckets):
    return mommy.make("api.AppS3Bucket", app=app, s3bucket=s3buckets["connected"])


@pytest.fixture
def fixture_create_update_secret():
    with patch(
        "controlpanel.api.cluster.App.create_or_update_secret"
    ) as create_or_update:
        yield create_or_update


@pytest.fixture
def fixture_delete_secret():
    with patch(
        "controlpanel.api.cluster.App.delete_secret"
    ) as delete_env_var:
        yield delete_env_var


def add_update_secret(client, app, data):
    return client.post(reverse("create-app-secret", kwargs=dict(pk=app.id)), data)


def delete_secret_post(client, app, key, data):
    return client.post(
        reverse("delete-app-secret", kwargs={"pk": app.id, "secret_name": key}), data
    )


@pytest.mark.parametrize(  # noqa: F405
    "user,expected_status",
    [["superuser", 302],
     ["app_admin", 302],
     ["normal_user", 403]],
)
def test_add_secret_permissions(
    client, app, users, fixture_create_update_secret, user, expected_status
):
    data = {"env_name": ["dev"],
            "key": ['NEW_SECRET'],
            "value": ['testing']}
    client.force_login(users[user])
    response = add_update_secret(client, app, data=data)
    assert response.status_code == expected_status


@pytest.mark.parametrize(  # noqa: F405
    "user, key, data, expected_status, expected_calls",
    [["superuser", "testing", {"env_name": "testing"}, 302, 1],
     ["app_admin", "testing", {}, 302, 1],
     ["normal_user", "testing", {}, 403, 0]],
)
def test_delete_secret(
    client, app, users, fixture_delete_secret, user, key, data, expected_status,
    expected_calls
):
    client.force_login(users[user])
    response = delete_secret_post(client, app, key, data)
    assert response.status_code == expected_status
    assert fixture_delete_secret.call_count == expected_calls


def test_add_secret(fixture_create_update_secret,
    client, app, users
):
    client.force_login(users['superuser'])
    data = {"env_name": ["dev"],
            "key": ['NEW_SECRET'],
            "value": ['testing']}
    response = add_update_secret(client, app, data=data)
    assert response.status_code == 302
    fixture_create_update_secret.assert_called_with(
        env_name='dev',
        secret_key=f"{settings.APP_SELF_DEFINE_SETTING_PREFIX}NEW_SECRET",
        secret_value='testing')
