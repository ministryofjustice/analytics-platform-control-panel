# Standard library
from unittest.mock import patch
import requests

# Third-party
import pytest
from django.contrib.messages import get_messages
from django.urls import reverse
from model_mommy import mommy
from rest_framework import status

# First-party/Local
from controlpanel.api import auth0
from tests.api.fixtures.aws import *

NUM_APPS = 3


@pytest.fixture(autouse=True)
def enable_db_for_all_tests(db):
    pass


@pytest.yield_fixture(autouse=True)
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


@pytest.fixture(autouse=True)
def users(users):
    users.update(
        {
            "app_admin": mommy.make("api.User", username="app_admin"),
        }
    )
    return users


@pytest.fixture(autouse=True)
def app(users):
    mommy.make("api.App", NUM_APPS - 1)
    app = mommy.make("api.App")
    app.repo_url = "https://github.com/github_org/testing_repo"
    app.save()
    mommy.make("api.UserApp", user=users["app_admin"], app=app, is_admin=True)
    return app


@pytest.yield_fixture(autouse=True)
def githubapi():
    """
    Mock calls to Github
    """
    with patch("controlpanel.frontend.forms.GithubAPI"), \
            patch("controlpanel.api.cluster.GithubAPI") as GithubAPI:
        yield GithubAPI.return_value


@pytest.yield_fixture(autouse=True)
def repos(githubapi):
    test_repo = {
        "full_name": "Test App",
        "html_url": "https://github.com/moj-analytical-services/test_app",
    }
    githubapi.get_repository.return_value = test_repo
    githubapi.get_repo_envs.return_value = ["test"]
    yield githubapi


@pytest.fixture(autouse=True)
def s3buckets(app):
    with patch("controlpanel.api.aws.AWSBucket.create_bucket") as _:
        buckets = {
            "not_connected": mommy.make("api.S3Bucket"),
            "connected": mommy.make("api.S3Bucket"),
        }
        return buckets


@pytest.fixture
def apps3bucket(app, s3buckets):
    with patch("controlpanel.api.aws.AWSRole.grant_bucket_access"):
        return mommy.make("api.AppS3Bucket", app=app, s3bucket=s3buckets["connected"])


def list_apps(client, *args):
    return client.get(reverse("list-apps"))


def list_all(client, *args):
    return client.get(reverse("list-all-apps"))


def detail(client, app, *args):
    return client.get(reverse("manage-app", kwargs={"pk": app.id}))


def update_auth0_connections(client, app, *args):
    return client.get(reverse("update-auth0-connections", kwargs={"pk": app.id}))


def create(client, *args):
    data = {
        "repo_url": "https://github.com/moj-analytical-services/test_app",
        "connect_bucket": "later",
        "disable_authentication": False,
    }
    return client.post(reverse("create-app"), data)


def delete(client, app, *args):
    return client.post(reverse("delete-app", kwargs={"pk": app.id}))


def add_admin(client, app, users, *args):
    data = {
        "user_id": users["other_user"].auth0_id,
    }
    return client.post(reverse("add-app-admin", kwargs={"pk": app.id}), data)


def revoke_admin(client, app, users, *args):
    kwargs = {
        "pk": app.id,
        "user_id": users["app_admin"].auth0_id,
    }
    return client.post(reverse("revoke-app-admin", kwargs=kwargs))


def add_customers(client, app, *args):
    data = {
        "customer_email": "test@example.com",
    }
    return client.post(reverse("add-app-customers", kwargs={"pk": app.id}), data)


def remove_customers(client, app, *args):
    data = {
        "customer": "email|user_1",
    }
    return client.post(reverse("remove-app-customer", kwargs={"pk": app.id}), data)


def connect_bucket(client, app, _, s3buckets, *args):
    data = {
        "datasource": s3buckets["not_connected"].id,
        "access_level": "readonly",
    }
    return client.post(reverse("grant-app-access", kwargs={"pk": app.id}), data)


def update_ip_allowlists(client, app, *args):
    return client.post(reverse("update-app-ip-allowlists", kwargs={"pk": app.id}))


@pytest.mark.parametrize(
    "view,user,expected_status",
    [
        (list_apps, "superuser", status.HTTP_200_OK),
        (list_apps, "app_admin", status.HTTP_200_OK),
        (list_apps, "normal_user", status.HTTP_200_OK),
        (list_all, "superuser", status.HTTP_200_OK),
        (list_all, "app_admin", status.HTTP_403_FORBIDDEN),
        (list_all, "normal_user", status.HTTP_403_FORBIDDEN),
        (detail, "superuser", status.HTTP_200_OK),
        (detail, "app_admin", status.HTTP_200_OK),
        (detail, "normal_user", status.HTTP_403_FORBIDDEN),
        (update_auth0_connections, "superuser", status.HTTP_200_OK),
        (update_auth0_connections, "app_admin", status.HTTP_403_FORBIDDEN),
        (update_auth0_connections, "normal_user", status.HTTP_403_FORBIDDEN),
        (create, "superuser", status.HTTP_200_OK),
        (create, "app_admin", status.HTTP_403_FORBIDDEN),
        (create, "normal_user", status.HTTP_403_FORBIDDEN),
        (delete, "superuser", status.HTTP_302_FOUND),
        (delete, "app_admin", status.HTTP_403_FORBIDDEN),
        (delete, "normal_user", status.HTTP_403_FORBIDDEN),
        (add_admin, "superuser", status.HTTP_302_FOUND),
        (add_admin, "app_admin", status.HTTP_302_FOUND),
        (add_admin, "normal_user", status.HTTP_403_FORBIDDEN),
        (revoke_admin, "superuser", status.HTTP_302_FOUND),
        (revoke_admin, "app_admin", status.HTTP_302_FOUND),
        (revoke_admin, "normal_user", status.HTTP_403_FORBIDDEN),
        (add_customers, "superuser", status.HTTP_302_FOUND),
        (add_customers, "app_admin", status.HTTP_302_FOUND),
        (add_customers, "normal_user", status.HTTP_403_FORBIDDEN),
        (remove_customers, "superuser", status.HTTP_302_FOUND),
        (remove_customers, "app_admin", status.HTTP_302_FOUND),
        (remove_customers, "normal_user", status.HTTP_403_FORBIDDEN),
        (connect_bucket, "superuser", status.HTTP_302_FOUND),
        (connect_bucket, "app_admin", status.HTTP_403_FORBIDDEN),
        (connect_bucket, "normal_user", status.HTTP_403_FORBIDDEN),
        (update_ip_allowlists, "superuser", status.HTTP_302_FOUND),
        (update_ip_allowlists, "app_admin", status.HTTP_302_FOUND),
        (update_ip_allowlists, "normal_user", status.HTTP_403_FORBIDDEN),
    ],
)
def test_permissions(
    client,
    app,
    s3buckets,
    users,
    view,
    user,
    expected_status,
    fixture_get_group_id
):
    with patch("controlpanel.api.aws.AWSRole.grant_bucket_access"), \
            patch("controlpanel.api.cluster.App.create_or_update_secret"):
        client.force_login(users[user])
        print(users[user])
        print(users[user].has_perm('api.add_app_customer', app))
        response = view(client, app, users, s3buckets)
        assert response.status_code == expected_status


def disconnect_bucket(client, apps3bucket, *args, **kwargs):
    return client.post(reverse("revoke-app-access", kwargs={"pk": apps3bucket.id}))


@pytest.mark.parametrize(
    "view,user,expected_status",
    [
        (disconnect_bucket, "superuser", status.HTTP_302_FOUND),
        (disconnect_bucket, "app_admin", status.HTTP_403_FORBIDDEN),
        (disconnect_bucket, "normal_user", status.HTTP_403_FORBIDDEN),
    ],
)
def test_bucket_permissions(client, apps3bucket, users, view, user, expected_status):
    client.force_login(users[user])
    response = view(client, apps3bucket, users)
    assert response.status_code == expected_status


@pytest.mark.parametrize(
    "view,user,expected_count",
    [
        (list_apps, "superuser", 0),
        (list_apps, "normal_user", 0),
        (list_apps, "app_admin", 1),
        (list_all, "superuser", NUM_APPS),
    ],
)
def test_list(client, app, users, view, user, expected_count):
    client.force_login(users[user])
    response = view(client, app, users)
    assert len(response.context_data["object_list"]) == expected_count


def add_customer_success(client, response):
    return "add_customer_form_errors" not in client.session


def add_customer_form_error(client, response):
    return "add_customer_form_errors" in client.session


@pytest.mark.parametrize(
    "emails, expected_response",
    [
        ("foo@example.com", add_customer_success),
        ("foo@example.com, bar@example.com", add_customer_success),
        ("foobar", add_customer_form_error),
        ("foo@example.com, foobar", add_customer_form_error),
        ("", add_customer_form_error),
    ],
    ids=[
        "single-valid-email",
        "multiple-delimited-emails",
        "invalid-email",
        "mixed-valid-invalid-emails",
        "no-emails",
    ],
)
def test_add_customers(client, app, users, emails, expected_response):
    client.force_login(users["superuser"])
    data = {"customer_email": emails, "env_name": "test_env"}
    response = client.post(reverse("add-app-customers", kwargs={"pk": app.id}), data)
    assert expected_response(client, response)


def remove_customer_success(client, response):
    messages = [str(m) for m in get_messages(response.wsgi_request)]
    return "Successfully removed customer" in messages


def remove_customer_failure(client, response):
    messages = [str(m) for m in get_messages(response.wsgi_request)]
    return "Failed removing customer" in messages


@pytest.yield_fixture
def fixture_delete_group_members(ExtendedAuth0):
    with patch.object(ExtendedAuth0.groups, "delete_group_members") as request:
        yield request


@pytest.mark.parametrize(
    "side_effect, expected_response",
    [
        (None, remove_customer_success),
        (auth0.Auth0Error, remove_customer_failure),
    ],
    ids=[
        "success",
        "failure",
    ],
)
def test_delete_customers(
    client, app, fixture_delete_group_members, users, side_effect, expected_response
):
    fixture_delete_group_members.side_effect = side_effect
    client.force_login(users["superuser"])
    data = {"customer": ["email|1234"]}
    response = client.post(reverse("remove-app-customer", kwargs={"pk": app.id}), data)
    assert expected_response(client, response)


def test_github_error1_on_app_detail(client, app, users,):
    with patch('django.conf.settings.features.app_migration.enabled') as feature_flag, \
            patch("controlpanel.api.cluster.App.get_deployment_envs") as get_envs:
        feature_flag.return_value = True
        error_msg = "Testing github error"
        get_envs.side_effect = requests.exceptions.HTTPError(error_msg)
        client.force_login(users["superuser"])
        response = detail(client, app)
        assert response.status_code == 200
        assert error_msg in str(response.content)


def test_github_error2_on_app_detail(client, app, users,):
    with patch('django.conf.settings.features.app_migration.enabled') as feature_flag, \
            patch("controlpanel.api.cluster.App.get_env_secrets") as get_secrets:
        feature_flag.return_value = True
        error_msg = "Testing github secret error"
        get_secrets.side_effect = requests.exceptions.HTTPError(error_msg)
        client.force_login(users["superuser"])
        response = detail(client, app)
        assert response.status_code == 200
        assert error_msg in str(response.content)


def test_github_error3_on_app_detail(client, app, users,):
    with patch('django.conf.settings.features.app_migration.enabled') as feature_flag, \
            patch("controlpanel.api.cluster.App.get_env_secrets") as get_secrets, \
            patch("controlpanel.api.cluster.App.get_env_vars") as get_env_vars:
        feature_flag.return_value = True
        error_msg = "Testing github env error"
        get_secrets.return_value = [{"name": "testing_github_secret"}]
        get_env_vars.side_effect = requests.exceptions.HTTPError(error_msg)
        client.force_login(users["superuser"])
        response = detail(client, app)
        assert response.status_code == 200
        assert error_msg in str(response.content)


@pytest.fixture
def app_being_migrated(users):
    app = mommy.make("api.App")
    app.repo_url = "https://github.com/new_github_org/testing_repo"
    app_old_repo_url = "https://github.com/github_org/testing_repo"
    migration_json = dict(
        app_name="testing_app",
        repo_url=app_old_repo_url,
        app_url=f"https://{app.slug}.{settings.APP_DOMAIN}",
        state="in_process"
    )
    app_info = dict(
        migration=migration_json
    )
    app.description = json.dumps(app_info)
    app.save()
    mommy.make("api.UserApp", user=users["app_admin"], app=app, is_admin=True)
    return app


def test_app_description_display_old_app_info(client, app_being_migrated, users):
    with patch('django.conf.settings.features.app_migration.enabled') as feature_flag:
        feature_flag.return_value = True
        client.force_login(users["superuser"])
        response = detail(client, app_being_migrated)
        assert response.status_code == 200
        assert app_being_migrated.migration_info["app_name"] in str(response.content)
        assert app_being_migrated.migration_info["repo_url"] in str(response.content)
        assert app_being_migrated.migration_info["app_url"] in str(response.content)
