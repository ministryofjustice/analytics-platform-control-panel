# Standard library
import json
import uuid
from unittest.mock import call, patch

# Third-party
import botocore
import pytest
import requests
from bs4 import BeautifulSoup
from django.conf import settings
from django.contrib.messages import Message, constants, get_messages
from django.urls import reverse
from model_bakery import baker
from pytest_django.asserts import assertMessages, assertQuerySetEqual
from rest_framework import status

# First-party/Local
from controlpanel.api import auth0, cluster
from controlpanel.api.github import RepositoryNotFound
from controlpanel.api.models import App, AppIPAllowList, S3Bucket
from controlpanel.api.models.app import DeleteCustomerError
from tests.api.fixtures.aws import *

NUM_APPS = 3


@pytest.fixture(autouse=True)
def enable_db_for_all_tests(db):
    pass


@pytest.fixture(autouse=True)
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


@pytest.fixture
def users(users):
    users.update(
        {
            "app_admin": baker.make("api.User", auth0_id="github|user", username="app_admin"),
        }
    )
    return users


@pytest.fixture
def app(users, iam):
    ip_allowlists = [
        baker.make("api.IPAllowlist", allowed_ip_ranges="xyz"),
    ]
    baker.make("api.App", NUM_APPS - 1)
    app = baker.make("api.App")
    app.repo_url = "https://github.com/github_org/testing_repo"
    dev_auth_settings = dict(client_id="dev_client_id", group_id=str(uuid.uuid4()))
    prod_auth_settings = dict(client_id="prod_client_id", group_id=str(uuid.uuid4()))
    env_app_settings = dict(
        dev_env=dev_auth_settings,
        prod_env=prod_auth_settings,
    )
    app.app_conf = {App.KEY_WORD_FOR_AUTH_SETTINGS: env_app_settings}
    app.save()
    AppIPAllowList.objects.update_records(app, "dev_env", ip_allowlists)
    baker.make("api.UserApp", user=users["app_admin"], app=app, is_admin=True)
    test_policy = {
        "Sid": "TestAssumeRolePolicy",
        "Effect": "Allow",
        "Action": "sts:AssumeRole",
        "Principal": {"AWS": "arn:aws:iam::123456789012:role/some-role"},
        "Condition": {},
    }
    iam.create_role(RoleName=app.iam_role_name, AssumeRolePolicyDocument=json.dumps(test_policy))
    return app


@pytest.fixture(autouse=True)
def githubapi():
    """
    Mock calls to Github
    """
    with (
        patch("controlpanel.frontend.forms.GithubAPI") as forms_githubapi,
        patch("controlpanel.frontend.views.app.GithubAPI") as views_githubapi,
        patch("controlpanel.api.cluster.GithubAPI") as cluster_githubapi,
    ):
        yield {
            "forms": forms_githubapi.return_value,
            "views": views_githubapi.return_value,
            "cluster": cluster_githubapi.return_value,
        }


@pytest.fixture
def repos(githubapi):
    test_repo = {
        "full_name": "Test App",
        "html_url": "https://github.com/moj-analytical-services/test_app",
    }
    githubapi["cluster"].get_repository.return_value = test_repo
    githubapi["cluster"].get_repo_envs.return_value = ["dev_env", "prod_env"]
    githubapi["cluster"].get_repo_env_vars.return_value = [
        {"name": cluster.App.AUTHENTICATION_REQUIRED, "value": "True"},
        {"name": f"{settings.APP_SELF_DEFINE_SETTING_PREFIX}PARAM_VAR", "value": "test_var"},
    ]
    githubapi["cluster"].get_repo_env_secrets.return_value = [
        {"name": cluster.App.IP_RANGES},
        {"name": f"{settings.APP_SELF_DEFINE_SETTING_PREFIX}PARAM_SECRET"},
    ]
    yield githubapi


@pytest.fixture
def repos_with_auth(githubapi):
    test_repo = {
        "full_name": "Test App",
        "html_url": "https://github.com/moj-analytical-services/test_app",
    }
    githubapi["cluster"].get_repository.return_value = test_repo
    githubapi["cluster"].get_repo_envs.return_value = ["dev_env"]
    githubapi["cluster"].get_repo_env_vars.return_value = [
        {"name": cluster.App.AUTHENTICATION_REQUIRED, "value": "True"},
        {"name": cluster.App.AUTH0_DOMAIN, "value": "http://testing"},
    ]
    githubapi["cluster"].get_repo_env_secrets.return_value = [
        {"name": cluster.App.APP_ROLE_ARN},
        {"name": cluster.App.AUTH0_CLIENT_ID},
        {"name": cluster.App.AUTH0_CLIENT_SECRET},
        {"name": cluster.App.IP_RANGES},
    ]
    yield githubapi["cluster"]


@pytest.fixture
def repos_for_missing_auth(githubapi):
    test_repo = {
        "full_name": "Test App",
        "html_url": "https://github.com/moj-analytical-services/test_app",
    }
    githubapi["cluster"].get_repository.return_value = test_repo
    githubapi["cluster"].get_repo_envs.return_value = ["dev_env"]
    githubapi["cluster"].get_repo_env_vars.return_value = [
        {"name": cluster.App.AUTHENTICATION_REQUIRED, "value": "True"}
    ]
    yield githubapi["cluster"]


@pytest.fixture
def repos_for_no_auth(githubapi):
    test_repo = {
        "full_name": "Test App",
        "html_url": "https://github.com/moj-analytical-services/test_app",
    }
    githubapi["cluster"].get_repository.return_value = test_repo
    githubapi["cluster"].get_repo_envs.return_value = ["dev_env"]
    githubapi["cluster"].get_repo_env_vars.return_value = [
        {"name": cluster.App.AUTHENTICATION_REQUIRED, "value": "False"},
    ]
    githubapi["cluster"].get_repo_env_secrets.return_value = [
        {"name": cluster.App.IP_RANGES},
        {"name": cluster.App.APP_ROLE_ARN},
    ]
    yield githubapi["cluster"]


@pytest.fixture
def repos_for_redundant_auth(githubapi):
    test_repo = {
        "full_name": "Test App",
        "html_url": "https://github.com/moj-analytical-services/test_app",
    }
    githubapi["cluster"].get_repository.return_value = test_repo
    githubapi["cluster"].get_repo_envs.return_value = ["dev_env"]
    githubapi["cluster"].get_repo_env_vars.return_value = [
        {"name": cluster.App.AUTHENTICATION_REQUIRED, "value": "False"}
    ]
    githubapi["cluster"].get_repo_env_secrets.return_value = [
        {"name": cluster.App.AUTH0_CLIENT_ID},
        {"name": cluster.App.AUTH0_CLIENT_SECRET},
    ]
    yield githubapi["cluster"]


@pytest.fixture(autouse=True)
def s3buckets(app, users):
    with patch("controlpanel.api.aws.AWSBucket.create") as _:
        buckets = {
            "not_connected": baker.make("api.S3Bucket", created_by=users["app_admin"]),
            "connected": baker.make("api.S3Bucket", created_by=users["app_admin"]),
        }
        return buckets


@pytest.fixture
def apps3bucket(app, s3buckets):
    with patch("controlpanel.api.aws.AWSRole.grant_bucket_access"):
        return baker.make("api.AppS3Bucket", app=app, s3bucket=s3buckets["connected"])


def list_apps(client, *args):
    return client.get(reverse("list-apps"))


def list_all(client, *args):
    return client.get(reverse("list-all-apps"))


def admin_csv(client, app, *args):
    return client.post(reverse("app-admin-csv"))


def detail(client, app, *args):
    return client.get(reverse("manage-app", kwargs={"pk": app.id}))


def update_auth0_connections(client, app, *args):
    return client.get(reverse("update-auth0-connections", kwargs={"pk": app.id}))


def create(client, *args):
    return client.get(reverse("create-app"))


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
    return client.post(
        reverse("add-app-customers", args=(app.id, app.get_group_id("dev_env"))), data
    )


def remove_customers(client, app, *args):
    data = {
        "customer": "email|user_1",
    }
    return client.post(
        reverse("remove-app-customer", args=(app.id, app.get_group_id("dev_env"))), data
    )


def remove_customer_by_email(client, app, *args):
    return client.post(
        reverse("remove-app-customer-by-email", args=(app.id, app.get_group_id("dev_env"))), data={}
    )


def set_cloud_platform_arn(client, app, *args):

    data = {
        "allow_cloud_platform_assume_role": True,
        "cloud_platform_role_arn": "arn:aws:iam::123456789012:role/test-role",
    }

    return client.post(reverse("set-cloud-platform-arn", kwargs={"pk": app.id}), data)


def connect_bucket(client, app, _, s3buckets, *args):
    data = {
        "datasource": s3buckets["not_connected"].id,
        "access_level": "readonly",
    }
    return client.post(reverse("grant-app-access", kwargs={"pk": app.id}), data)


def update_ip_allowlists(client, app, *args):
    return client.post(reverse("update-app-ip-allowlists", kwargs={"pk": app.id}))


def set_bedrock(client, app, *args):
    data = {
        "is_bedrock_enabled": True,
    }
    kwargs = {"pk": app.id}
    return client.post(reverse("set-bedrock-app", kwargs=kwargs), data)


def set_textract(client, app, *args):
    data = {
        "is_textract_enabled": True,
    }
    kwargs = {"pk": app.id}
    return client.post(reverse("set-textract-app", kwargs=kwargs), data)


@patch("controlpanel.api.cluster.App.create_m2m_client")
def setup_m2m_client(client, app, *args):
    kwargs = {"pk": app.id}
    return client.post(reverse("create-m2m-client", kwargs=kwargs))


def rotate_m2m_credentials(client, app, *args):
    kwargs = {"pk": app.id}
    return client.post(reverse("rotate-m2m-credentials", kwargs=kwargs))


def delete_m2m_client(client, app, *args):
    kwargs = {"pk": app.id}
    return client.post(reverse("delete-m2m-client", kwargs=kwargs))


@pytest.mark.parametrize(
    "view,user,expected_status",
    [
        (list_apps, "superuser", status.HTTP_200_OK),
        (list_apps, "app_admin", status.HTTP_200_OK),
        (list_apps, "normal_user", status.HTTP_200_OK),
        (list_all, "superuser", status.HTTP_200_OK),
        (list_all, "app_admin", status.HTTP_403_FORBIDDEN),
        (list_all, "normal_user", status.HTTP_403_FORBIDDEN),
        (admin_csv, "superuser", status.HTTP_200_OK),
        (admin_csv, "app_admin", status.HTTP_403_FORBIDDEN),
        (admin_csv, "normal_user", status.HTTP_403_FORBIDDEN),
        (detail, "superuser", status.HTTP_200_OK),
        (detail, "app_admin", status.HTTP_200_OK),
        (detail, "normal_user", status.HTTP_403_FORBIDDEN),
        (update_auth0_connections, "superuser", status.HTTP_200_OK),
        (update_auth0_connections, "app_admin", status.HTTP_403_FORBIDDEN),
        (update_auth0_connections, "normal_user", status.HTTP_403_FORBIDDEN),
        (create, "superuser", status.HTTP_200_OK),
        (create, "app_admin", status.HTTP_200_OK),
        (create, "normal_user", status.HTTP_200_OK),
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
        (remove_customer_by_email, "superuser", status.HTTP_302_FOUND),
        (remove_customer_by_email, "app_admin", status.HTTP_302_FOUND),
        (remove_customer_by_email, "normal_user", status.HTTP_403_FORBIDDEN),
        (connect_bucket, "superuser", status.HTTP_302_FOUND),
        (connect_bucket, "app_admin", status.HTTP_302_FOUND),
        (connect_bucket, "normal_user", status.HTTP_403_FORBIDDEN),
        (update_ip_allowlists, "superuser", status.HTTP_302_FOUND),
        (update_ip_allowlists, "app_admin", status.HTTP_302_FOUND),
        (update_ip_allowlists, "normal_user", status.HTTP_403_FORBIDDEN),
        (set_bedrock, "superuser", status.HTTP_302_FOUND),
        (set_bedrock, "app_admin", status.HTTP_403_FORBIDDEN),
        (set_bedrock, "normal_user", status.HTTP_403_FORBIDDEN),
        (set_textract, "superuser", status.HTTP_302_FOUND),
        (set_textract, "app_admin", status.HTTP_403_FORBIDDEN),
        (set_textract, "normal_user", status.HTTP_403_FORBIDDEN),
        (setup_m2m_client, "superuser", status.HTTP_302_FOUND),
        (setup_m2m_client, "app_admin", status.HTTP_302_FOUND),
        (setup_m2m_client, "normal_user", status.HTTP_403_FORBIDDEN),
        (rotate_m2m_credentials, "superuser", status.HTTP_302_FOUND),
        (rotate_m2m_credentials, "app_admin", status.HTTP_302_FOUND),
        (rotate_m2m_credentials, "normal_user", status.HTTP_403_FORBIDDEN),
        (delete_m2m_client, "superuser", status.HTTP_302_FOUND),
        (delete_m2m_client, "app_admin", status.HTTP_302_FOUND),
        (delete_m2m_client, "normal_user", status.HTTP_403_FORBIDDEN),
        (set_cloud_platform_arn, "superuser", status.HTTP_302_FOUND),
        (set_cloud_platform_arn, "app_admin", status.HTTP_302_FOUND),
        (set_cloud_platform_arn, "normal_user", status.HTTP_403_FORBIDDEN),
    ],
)
def test_permissions(
    client, app, s3buckets, users, iam, view, user, expected_status, fixture_get_group_id
):
    with (
        patch("controlpanel.api.aws.AWSRole.grant_bucket_access"),
        patch("controlpanel.api.cluster.App.create_or_update_secret"),
    ):
        client.force_login(users[user])
        response = view(client, app, users, s3buckets, iam)
        assert response.status_code == expected_status


def test_admin_csv(client, app, users):
    client.force_login(users["superuser"])
    response = admin_csv(client, app)
    content = response.content.decode("utf-8")
    assert "App Name,Repo URL,Admins,Emails" in content
    assert app.name in content


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
    data = {"customer_email": emails, "env_name": "dev_env"}
    response = client.post(
        reverse(
            "add-app-customers", kwargs={"pk": app.id, "group_id": app.get_group_id("dev_env")}
        ),
        data,
    )
    assert expected_response(client, response)


def remove_customer_success(client, response):
    messages = [str(m) for m in get_messages(response.wsgi_request)]
    return "Successfully removed customer" in messages


def remove_customer_failure(client, response):
    messages = [str(m) for m in get_messages(response.wsgi_request)]
    return "Failed removing customer" in messages


@pytest.fixture
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

    response = client.post(
        reverse("remove-app-customer", args=(app.id, app.get_group_id("dev_env"))), data
    )
    assert expected_response(client, response)


def test_delete_cutomer_by_email_invalid_email(client, app, users):
    client.force_login(users["superuser"])
    url = reverse("remove-app-customer-by-email", args=(app.id, app.get_group_id("dev_env")))
    response = client.post(
        url,
        data={
            "remove-email": "notanemail",
            "remove-env_name": "test",
            "remove-group_id": "123",
        },
    )
    messages = [str(m) for m in get_messages(response.wsgi_request)]
    assert response.status_code == 302
    assert "Invalid email address entered" in messages


@pytest.mark.parametrize(
    "side_effect, expected_message",
    [
        (None, "Successfully removed customer email@example.com"),
        # fallback to display generic message if raised without one
        (DeleteCustomerError(), "Couldn't remove customer with email email@example.com"),
        # specific error message displayed
        (DeleteCustomerError("API error"), "API error"),
    ],
)
def test_delete_customer_by_email(client, app, users, side_effect, expected_message):
    client.force_login(users["superuser"])
    url = reverse("remove-app-customer-by-email", args=(app.id, app.get_group_id("dev_env")))
    with patch("controlpanel.frontend.views.app.App.delete_customer_by_email") as delete_by_email:
        delete_by_email.side_effect = side_effect
        response = client.post(
            url,
            data={
                "remove-email": "email@example.com",
                "remove-env_name": "test",
                "remove-group_id": "123",
            },
        )
        delete_by_email.assert_called_once()
        messages = [str(m) for m in get_messages(response.wsgi_request)]
        assert response.status_code == 302
        assert expected_message in messages


def test_github_error1_on_app_detail(
    client,
    app,
    users,
):
    with patch("controlpanel.api.cluster.App.get_deployment_envs") as get_envs:
        error_msg = "Testing github error"
        get_envs.side_effect = requests.exceptions.HTTPError(error_msg)
        client.force_login(users["superuser"])
        response = detail(client, app)
        assert response.status_code == 200
        assert error_msg in str(response.content)


def test_github_error2_on_app_detail(client, app, users, repos):
    with patch("controlpanel.api.cluster.App.get_env_secrets") as get_secrets:
        error_msg = "Testing github secret error"
        get_secrets.side_effect = requests.exceptions.HTTPError(error_msg)
        client.force_login(users["superuser"])
        response = detail(client, app)
        assert response.status_code == 200
        assert error_msg in str(response.content)


def test_github_error3_on_app_detail(client, app, users, repos):
    with (
        patch("controlpanel.api.cluster.App.get_env_secrets") as get_secrets,
        patch("controlpanel.api.cluster.App.get_env_vars") as get_env_vars,
    ):
        error_msg = "Testing github env error"
        get_secrets.return_value = [{"name": "testing_github_secret"}]
        get_env_vars.side_effect = requests.exceptions.HTTPError(error_msg)
        client.force_login(users["superuser"])
        response = detail(client, app)
        assert response.status_code == 200
        assert error_msg in str(response.content)


def test_app_detail_display_all_envs(client, app, users, repos):
    client.force_login(users["superuser"])
    response = detail(client, app)
    assert response.status_code == 200

    key_words_for_checks = [
        "Deployment settings under dev_env",
        "Deployment settings under prod_env",
        cluster.App.IP_RANGES,
        cluster.App.AUTH0_CLIENT_ID,
        cluster.App.AUTH0_CLIENT_SECRET,
        cluster.App.AUTH0_DOMAIN,
        cluster.App.AUTH0_CONNECTIONS,
        cluster.App.AUTHENTICATION_REQUIRED,
        cluster.App.AUTH0_PASSWORDLESS,
    ]
    for key_word in key_words_for_checks:
        assert key_word in str(response.content)


def test_app_detail_with_missing_auth_client(client, users, repos_for_missing_auth):
    app = baker.make("api.App")
    app.repo_url = "https://github.com/github_org/testing_repo_with_auth"
    app.save()

    client.force_login(users["superuser"])
    response = detail(client, app)
    btn_text = "Create auth0 client"
    assert response.status_code == 200
    assert btn_text in str(response.content)


def test_app_detail_with_auth_client_redundant(client, users, app, repos_for_redundant_auth):
    client.force_login(users["superuser"])
    response = detail(client, app)
    btn_text = "Remove auth0 client"
    assert response.status_code == 200
    assert btn_text in str(response.content)


@pytest.fixture
def app_being_migrated(users):
    app = baker.make("api.App")
    app.repo_url = "https://github.com/new_github_org/testing_repo"
    app_old_repo_url = "https://github.com/github_org/testing_repo"
    migration_json = dict(
        app_name="testing_app",
        repo_url=app_old_repo_url,
        app_url=f"https://{app.slug}.{settings.APP_DOMAIN}",
        status="in_progress",
    )
    app_info = dict(migration=migration_json)
    app.description = json.dumps(app_info)
    app.save()
    baker.make("api.UserApp", user=users["app_admin"], app=app, is_admin=True)
    return app


def get_auth_settings(content, env_name):
    soup = BeautifulSoup(content, "html.parser")
    setting_panel = soup.find("section", {"class": f"{env_name}-settings-panel"})
    return setting_panel.findAll("tr", {"class": "auth-setting-row"})


def locate_setting_ui(settings, setting_name):
    for item in settings:
        if setting_name in item.text:
            return item
    return None


def test_app_detail_with_auth_on(client, app, users, repos_with_auth):
    client.force_login(users["superuser"])
    response = detail(client, app)
    assert response.status_code == 200
    auth_settings = get_auth_settings(response.content, "dev_env")
    settings_for_checks = [
        {"n": cluster.App.IP_RANGES, "v": app.env_allowed_ip_ranges_names("dev_env"), "e": True},
        {"n": cluster.App.APP_ROLE_ARN, "v": app.iam_role_arn, "e": False},
        {"n": cluster.App.AUTH0_CLIENT_ID, "v": settings.SECRET_DISPLAY_VALUE, "e": False},
        {"n": cluster.App.AUTH0_CLIENT_SECRET, "v": settings.SECRET_DISPLAY_VALUE, "e": False},
        {"n": cluster.App.AUTH0_CONNECTIONS, "v": "[]", "e": True},
        {"n": cluster.App.AUTH0_DOMAIN, "v": "http://testing", "e": False},
        {"n": cluster.App.AUTH0_PASSWORDLESS, "v": "False", "e": False},
        {"n": cluster.App.AUTHENTICATION_REQUIRED, "v": "True", "e": True},
    ]
    for item in settings_for_checks:
        auth_item_ui = locate_setting_ui(auth_settings, item["n"])
        if not auth_item_ui:
            continue
        assert item["v"] in auth_item_ui.text
        if item["e"]:
            assert "Edit" in auth_item_ui.text
        else:
            assert "Edit" not in auth_item_ui.text


def test_app_detail_with_auth_off(client, app, users, repos_for_no_auth):
    client.force_login(users["superuser"])
    response = detail(client, app)
    assert response.status_code == 200

    settings_no_displayed = [
        cluster.App.AUTH0_DOMAIN,
        cluster.App.AUTH0_CLIENT_ID,
        cluster.App.AUTH0_CLIENT_SECRET,
        cluster.App.AUTH0_CONNECTIONS,
        cluster.App.AUTH0_PASSWORDLESS,
    ]

    auth_settings = get_auth_settings(response.content, "dev_env")
    for item in settings_no_displayed:
        auth_item_ui = locate_setting_ui(auth_settings, item)
        assert auth_item_ui is None

    settings_for_checks = [
        {"n": cluster.App.IP_RANGES, "v": app.env_allowed_ip_ranges_names("dev_env"), "e": True},
        {"n": cluster.App.APP_ROLE_ARN, "v": app.iam_role_arn, "e": False},
        {"n": cluster.App.AUTHENTICATION_REQUIRED, "v": "False", "e": True},
    ]
    for item in settings_for_checks:
        auth_item_ui = locate_setting_ui(auth_settings, item["n"])
        if not auth_item_ui:
            continue
        assert item["v"] in auth_item_ui.text
        if item["e"]:
            assert "Edit" in auth_item_ui.text
        else:
            assert "Edit" not in auth_item_ui.text


def test_app_detail_with_self_define_settings(client, app, users, repos):
    client.force_login(users["superuser"])
    response = detail(client, app)
    assert response.status_code == 200

    auth_settings = get_auth_settings(response.content, "dev_env")
    settings_for_checks = [
        {"n": "PARAM_SECRET", "v": settings.SECRET_DISPLAY_VALUE},
        {"n": "PARAM_VAR", "v": "test_var"},
    ]
    for item in settings_for_checks:
        auth_item_ui = locate_setting_ui(auth_settings, item["n"])
        if not auth_item_ui:
            continue
        setting_link = auth_item_ui.findAll("a")[0]["href"]
        assert f"{settings.APP_SELF_DEFINE_SETTING_PREFIX}{item['n']}" in setting_link
        assert item["v"] in auth_item_ui.text
        assert "Edit" in auth_item_ui.text


@pytest.mark.parametrize(
    "user,can_edit_connections",
    [
        ("superuser", True),
        ("app_admin", False),
    ],
)
def test_app_settings_permission(client, app, users, repos_with_auth, user, can_edit_connections):
    client.force_login(users[user])
    response = detail(client, app)
    assert response.status_code == 200
    auth_settings = get_auth_settings(response.content, "dev_env")
    settings_for_checks = [
        {"n": cluster.App.IP_RANGES, "v": app.env_allowed_ip_ranges_names("dev_env"), "e": True},
        {"n": cluster.App.AUTH0_CLIENT_ID, "v": settings.SECRET_DISPLAY_VALUE, "e": False},
        {"n": cluster.App.AUTH0_CLIENT_SECRET, "v": settings.SECRET_DISPLAY_VALUE, "e": False},
        {"n": cluster.App.AUTH0_CONNECTIONS, "v": "[]", "e": can_edit_connections},
        {"n": cluster.App.AUTH0_DOMAIN, "v": "http://testing", "e": False},
        {"n": cluster.App.AUTH0_PASSWORDLESS, "v": "False", "e": False},
        {"n": cluster.App.AUTHENTICATION_REQUIRED, "v": "True", "e": True},
    ]
    for item in settings_for_checks:
        auth_item_ui = locate_setting_ui(auth_settings, item["n"])
        if not auth_item_ui:
            continue
        assert item["v"] in auth_item_ui.text
        if item["e"]:
            assert "Edit" in auth_item_ui.text
        else:
            assert "Edit" not in auth_item_ui.text


def test_register_app_with_xacct_policy(client, users, githubapi):
    githubapi["views"].get_repository_contents.return_value = {"repo": "test-app-namespace-test"}
    test_app_name = "test_app_with_xacct_policy"
    assert App.objects.filter(name=test_app_name).count() == 0
    client.force_login(users["superuser"])
    data = dict(
        repo_url=f"https://github.com/ministryofjustice/{test_app_name}",
        namespace="test-app-namespace",
        connect_bucket="later",
        allow_cloud_platform_assume_role=True,
        cloud_platform_role_arn="arn:aws:iam::123456789012:role/test_role",
    )
    response = client.post(reverse("create-app"), data)

    assert response.status_code == 302
    assert App.objects.filter(name=test_app_name).count() == 1
    created_app = App.objects.filter(name=test_app_name).first()
    assert created_app.cloud_platform_role_arn == "arn:aws:iam::123456789012:role/test_role"
    assert response.url == reverse("manage-app", kwargs={"pk": created_app.pk})


def test_register_app_with_creating_datasource(client, users, githubapi):
    githubapi["views"].get_repository_contents.return_value = {"repo": "test-app-namespace-test"}
    test_app_name = "test_app_with_creating_datasource"
    test_bucket_name = "test-bucket"
    assert App.objects.filter(name=test_app_name).count() == 0
    client.force_login(users["superuser"])
    data = dict(
        repo_url=f"https://github.com/ministryofjustice/{test_app_name}",
        connect_bucket="new",
        new_datasource_name=test_bucket_name,
        namespace="test-app-namespace",
    )
    response = client.post(reverse("create-app"), data)

    assert response.status_code == 302
    assert App.objects.filter(name=test_app_name).count() == 1
    assert S3Bucket.objects.filter(name=test_bucket_name).count() == 1
    created_app = App.objects.filter(name=test_app_name).first()
    bucket = S3Bucket.objects.filter(name=test_bucket_name).first()
    related_bucket_ids = [a.s3bucket_id for a in created_app.apps3buckets.all()]
    assert len(related_bucket_ids) == 1
    assert bucket.id in related_bucket_ids
    assert response.url == reverse("manage-app", kwargs={"pk": created_app.pk})


def test_register_app_with_existing_datasource(client, users, s3buckets, githubapi):
    githubapi["views"].get_repository_contents.return_value = {"repo": "test-app-namespace-test"}
    test_app_name = "test_app_with_existing_datasource"
    existing_bucket = s3buckets["not_connected"]
    user = users["superuser"]
    assert App.objects.filter(name=test_app_name).count() == 0
    client.force_login(user)
    data = dict(
        repo_url=f"https://github.com/ministryofjustice/{test_app_name}",
        connect_bucket="existing",
        existing_datasource_id=existing_bucket.id,
        namespace="test-app-namespace",
    )
    response = client.post(reverse("create-app"), data)

    assert response.status_code == 302
    assert App.objects.filter(name=test_app_name).count() == 1
    assert S3Bucket.objects.filter(name=existing_bucket.name).count() == 1
    created_app = App.objects.filter(name=test_app_name).first()
    bucket = S3Bucket.objects.filter(name=existing_bucket.name).first()
    related_bucket_ids = [a.s3bucket_id for a in created_app.apps3buckets.all()]
    assert len(related_bucket_ids) == 1
    assert bucket.id in related_bucket_ids
    assert response.url == reverse("manage-app", kwargs={"pk": created_app.pk})


def test_register_app_invalid_organisation(client, users):
    client.force_login(users["superuser"])
    app_name = "example-app-old-org"
    data = dict(
        repo_url=f"https://github.com/moj-analytical-services/{app_name}",
        connect_bucket="later",
    )

    url = reverse("create-app")
    response = client.post(url, data)

    # 200 due to errors
    assert response.status_code == 200
    assert "repo_url" in response.context_data["form"].errors
    assert App.objects.filter(name=app_name).count() == 0


def test_register_app_invalid_namespace(client, users, githubapi):
    githubapi["views"].get_repository_contents.side_effect = RepositoryNotFound()
    client.force_login(users["superuser"])
    test_app_name = "test-app-with-invalid-namespace"
    data = dict(
        repo_url=f"https://github.com/ministryofjustice/{test_app_name}",
        namespace="test-app-namespace",
        connect_bucket="later",
    )

    url = reverse("create-app")
    response = client.post(url, data)

    # 200 due to namespace error
    assert response.status_code == 200
    assert "namespace" in response.context_data["form"].errors
    assert App.objects.filter(name=test_app_name).count() == 0
    githubapi["views"].get_repository_contents.assert_has_calls(
        [
            call(
                "cloud-platform-environments",
                f"namespaces/live.cloud-platform.service.justice.gov.uk/{data['namespace']}-dev",
            ),
            call(
                "cloud-platform-environments",
                f"namespaces/live.cloud-platform.service.justice.gov.uk/{data['namespace']}-prod",
            ),
        ]
    )


def test_register_app_with_valid_namespace(client, users, githubapi):
    githubapi["views"].get_repository_contents.return_value = {"repo": "test-app-dev"}
    client.force_login(users["superuser"])
    test_app_name = "test-app"
    data = dict(
        repo_url=f"https://github.com/ministryofjustice/{test_app_name}",
        namespace="test-app-namespace",
        connect_bucket="later",
    )

    url = reverse("create-app")
    response = client.post(url, data)

    # 302 due to successful creation
    assert response.status_code == 302
    # only one call to get_repository_contents as dev exists
    githubapi["views"].get_repository_contents.assert_called_once_with(
        "cloud-platform-environments",
        f"namespaces/live.cloud-platform.service.justice.gov.uk/{data['namespace']}-dev",
    )


def test_update_app_ip_allowlist_fails(app):
    original_app_allowlists = app.appipallowlists.all()
    new_allowlist = baker.make("api.IPAllowlist", allowed_ip_ranges="1.2.3.4")

    with patch("controlpanel.api.cluster.App.create_or_update_secret") as create_or_update_secret:
        create_or_update_secret.side_effect = requests.exceptions.HTTPError(
            "Error updating secret in GitHub"
        )

        with pytest.raises(requests.exceptions.HTTPError):
            AppIPAllowList.objects.update_ip_allowlist(
                app=app, env_name="dev_env", ip_allowlists=[new_allowlist]
            )

    assertQuerySetEqual(app.appipallowlists.all(), original_app_allowlists)
    assert (
        app.appipallowlists.filter(
            ip_allowlist__allowed_ip_ranges=new_allowlist.allowed_ip_ranges
        ).exists()
        is False
    )


@pytest.mark.parametrize("user", ["superuser", "app_admin"])
def test_create_m2m_client_success(app, users, client, user):
    user = users[user]
    client.force_login(user)
    url = reverse("create-m2m-client", kwargs={"pk": app.id})

    with patch("controlpanel.api.cluster.App.create_m2m_client") as m2m_client:
        m2m_client.return_value = {
            "client_id": "test-client-id",
            "client_secret": "test-client-secret",
        }
        response = client.post(url)

    m2m_client.assert_called_once()
    assert response.status_code == 302
    assert response.url == reverse("manage-app", kwargs={"pk": app.id})
    assertMessages(
        response,
        [
            Message(
                level=constants.SUCCESS,
                message="Successfully created machine-to-machine client. Your client credentials are shown below, ensure to store them securely as you will not be able to view them again.",  # noqa
            ),
            Message(level=constants.INFO, message="Client ID: test-client-id"),
            Message(level=constants.INFO, message="Client Secret: test-client-secret"),
        ],
        ordered=True,
    )


@pytest.mark.parametrize("user", ["superuser", "app_admin"])
def test_rotate_m2m_credentials_success(app, users, client, user):
    user = users[user]
    client.force_login(user)
    url = reverse("rotate-m2m-credentials", kwargs={"pk": app.id})

    with patch("controlpanel.api.cluster.App.rotate_m2m_client_secret") as m2m_client:
        m2m_client.return_value = {
            "client_id": "test-client-id",
            "client_secret": "test-client-secret",
        }
        response = client.post(url)

    m2m_client.assert_called_once()
    assert response.status_code == 302
    assert response.url == reverse("manage-app", kwargs={"pk": app.id})
    assertMessages(
        response,
        [
            Message(
                level=constants.SUCCESS,
                message="Successfully rotated machine-to-machine client secret. Your client ID and new client secret are shown below, ensure to store them securely as you will not be able to view them again.",  # noqa
            ),
            Message(level=constants.INFO, message="Client ID: test-client-id"),
            Message(level=constants.INFO, message="Client Secret: test-client-secret"),
        ],
        ordered=True,
    )


@pytest.mark.parametrize("user", ["superuser", "app_admin"])
def test_rotate_m2m_credentials_fails(app, users, client, user):
    user = users[user]
    client.force_login(user)
    url = reverse("rotate-m2m-credentials", kwargs={"pk": app.id})

    with patch("controlpanel.api.cluster.App.rotate_m2m_client_secret") as m2m_client:
        m2m_client.return_value = None
        response = client.post(url)

    m2m_client.assert_called_once()
    assert response.status_code == 302
    assert response.url == reverse("manage-app", kwargs={"pk": app.id})
    assertMessages(
        response,
        [
            Message(
                level=constants.ERROR,
                message="Failed to find a machine-to-machine client for this app, please try creating a new one.",  # noqa
            ),
        ],
        ordered=True,
    )


@pytest.mark.parametrize("user", ["superuser", "app_admin"])
def test_delete_m2m_client_success(app, users, client, user):
    user = users[user]
    client.force_login(user)
    url = reverse("delete-m2m-client", kwargs={"pk": app.id})

    with patch("controlpanel.api.cluster.App.delete_m2m_client") as delete_m2m_client:
        response = client.post(url)

    delete_m2m_client.assert_called_once()
    assert response.status_code == 302
    assert response.url == reverse("manage-app", kwargs={"pk": app.id})
    assertMessages(
        response,
        [
            Message(
                level=constants.SUCCESS,
                message="Successfully deleted machine-to-machine client.",  # noqa
            ),
        ],
        ordered=True,
    )


def test_add_cloud_platform_arn_success(app, users, client):
    user = users["superuser"]
    client.force_login(user)

    data = {
        "allow_cloud_platform_assume_role": True,
        "cloud_platform_role_arn": "arn:aws:iam::123456789012:role/test-role",
    }

    url = reverse("set-cloud-platform-arn", kwargs={"pk": app.id})

    response = client.post(url, data)

    assert response.status_code == 302
    assert response.url == reverse("manage-app", kwargs={"pk": app.id})
    obj = App.objects.get(pk=app.id)
    assert obj.cloud_platform_role_arn == data["cloud_platform_role_arn"]


@patch("controlpanel.api.cluster.App.update_trust_policy")
def test_add_cloud_platform_arn_fail(update_trust_policy_mock, app, users, client):
    update_trust_policy_mock.side_effect = botocore.exceptions.ClientError(
        operation_name="test_exception",
        error_response={"Error": {"Message": "Something Happened", "Code": "400"}},
    )
    user = users["superuser"]
    client.force_login(user)

    data = {
        "allow_cloud_platform_assume_role": True,
        "cloud_platform_role_arn": "arn:aws:iam::123456789012:role/test-role",
    }

    url = reverse("set-cloud-platform-arn", kwargs={"pk": app.id})

    response = client.post(url, data)

    assert response.status_code == 302
    assert response.url == reverse("manage-app", kwargs={"pk": app.id})
    obj = App.objects.get(pk=app.id)
    assert obj.cloud_platform_role_arn == ""
