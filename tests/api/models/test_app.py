# Standard library
from unittest.mock import call, patch

# Third-party
import pytest
from django.conf import settings
from model_bakery import baker

# First-party/Local
from controlpanel.api.auth0 import Auth0Error
from controlpanel.api.models import App


@pytest.fixture
def auth0():
    with patch("controlpanel.api.models.app.auth0") as auth0:
        auth0.Auth0Error = Auth0Error
        yield auth0


@pytest.fixture
def update_aws_secrets_manager():
    with patch(
        "controlpanel.api.cluster.App.create_or_update_secret"
    ) as update_aws_secrets_manager:
        yield update_aws_secrets_manager


@pytest.fixture
def app():
    app = baker.make("api.App")
    app.repo_url = "https://github.com/example.com/repo_name"
    auth_settings = dict(client_id="testing_client_id", group_id="testing_group_id")
    env_app_settings = dict(test_env=auth_settings)
    app.app_conf = {App.KEY_WORD_FOR_AUTH_SETTINGS: env_app_settings}
    app.save()
    return app


@pytest.mark.django_db
def test_create(sqs, helpers):
    repo_url = "https://example.com/foo__bar-baz!bat-1337"
    app = App.objects.create(repo_url=repo_url)
    iam_messages = helpers.retrieve_messages(sqs, queue_name=settings.IAM_QUEUE_NAME)
    helpers.validate_task_with_sqs_messages(
        iam_messages, App.__name__, app.id, queue_name=settings.IAM_QUEUE_NAME
    )


@pytest.mark.django_db
def test_slug_characters_replaced():
    repo_url = "https://example.com/foo__bar-baz!bat-1337"
    app = App.objects.create(repo_url=repo_url)
    assert "foo-bar-bazbat-1337" == app.slug


@pytest.mark.django_db
def test_slug_collisions_increments():
    app = App.objects.create(repo_url="git@github.com:org/foo-bar.git", namespace="foo-bar")
    assert "foo-bar" == app.slug

    app2 = App.objects.create(repo_url="https://www.example.com/org/foo-bar", namespace="foo-bar-2")
    assert "foo-bar-2" == app2.slug


@pytest.mark.django_db
def test_delete_also_deletes_app_artifacts(auth0):
    app = App.objects.create(repo_url="https://github.com/example.com/repo_name")

    with patch("controlpanel.api.models.app.cluster") as cluster:
        app.delete(github_api_token="testing")

        cluster.App.assert_called_with(app, "testing")
        cluster.App.return_value.delete.assert_called()


@pytest.mark.django_db
def test_get_customers(auth0):
    app = App.objects.create(repo_url="https://github.com/example.com/repo_name")
    authz = auth0.ExtendedAuth0.return_value
    authz.groups.get_group_members.return_value = [{"email": "test@example.com"}]
    env_name = "test_env"

    customers = app.customers(env_name)

    expected_emails = ["test@example.com"]
    assert expected_emails == [customer["email"] for customer in customers]


@pytest.mark.django_db
def test_add_customers(auth0, app):
    authz = auth0.ExtendedAuth0.return_value
    testing_env = "test_env"
    emails = ["test1@example.com", "test2@example.com"]

    app.add_customers(emails, env_name=testing_env)

    authz.add_group_members_by_emails.assert_called_with(
        emails=emails,
        user_options={"connection": "email"},
        group_id="testing_group_id",
    )


@pytest.mark.django_db
def test_delete_customers(auth0, app):
    authz = auth0.ExtendedAuth0.return_value
    app.delete_customers(["email|123"], env_name="test_env")
    authz.groups.delete_group_members.assert_called_with(
        user_ids=["email|123"],
        group_id="testing_group_id",
    )


@pytest.mark.parametrize(
    "url, expected_name",
    [
        ("https://github.com/org/a_repo_name", "a_repo_name"),
        ("git@github.com:org/repo_2.git", "repo_2"),
        ("https://github.com/org/a_repo_name.git/", "a_repo_name"),
        ("https://github.com/org/a_repo_name/", "a_repo_name"),
        ("http://foo.com", "foo.com"),
        ("http://foo.com/", "foo.com"),
    ],
)
def test_repo_name(url, expected_name):
    app = baker.prepare("api.App")
    app.repo_url = url
    assert app._repo_name == expected_name


@pytest.mark.parametrize(
    "side_effect, error_message",
    [
        (Auth0Error, Auth0Error.default_detail),
        (lambda email, connection: [], "Couldn't find user with email foo@email.com"),
    ],
)
def test_delete_customer_by_email_error_getting_user(auth0, side_effect, error_message):
    authz = auth0.ExtendedAuth0.return_value
    authz.users.get_users_email_search.side_effect = side_effect
    app = baker.prepare("api.App")
    with pytest.raises(app.DeleteCustomerError, match=error_message):
        app.delete_customer_by_email("foo@email.com", group_id="123")


def test_delete_customer_by_email_user_missing_group(auth0):
    user = {"user_id": "1"}
    user_groups = {"_id": "wrong_group"}

    authz = auth0.ExtendedAuth0.return_value
    authz.users.get_users_email_search.return_value = [user]
    authz.users.get_user_groups.return_value = [user_groups]

    app = baker.prepare("api.App")
    with pytest.raises(
        app.DeleteCustomerError,
        match="User foo@email.com cannot be found in this application group",
    ):
        app.delete_customer_by_email("foo@email.com", group_id="123")


def test_delete_customer_by_email_success(auth0):
    user = {"user_id": "1"}
    user_groups = {"_id": "123"}

    authz = auth0.ExtendedAuth0.return_value
    authz.users.get_users_email_search.return_value = [user]
    authz.users.get_user_groups.return_value = [user_groups]

    app = baker.prepare("api.App")

    with patch.object(app, "delete_customers") as delete_customers:
        app.delete_customer_by_email("foo@email.com", group_id="123")
        delete_customers.assert_called_once_with(
            user_ids=[user["user_id"]],
            group_id=user_groups["_id"],
        )


@pytest.mark.django_db
def test_app_allowed_ip_ranges():
    ip_allow_lists = [
        baker.make("api.IPAllowlist", allowed_ip_ranges="127.0.0.1, 128.10.10.100"),
        baker.make("api.IPAllowlist", allowed_ip_ranges=" 123.0.0.122,152.0.0.1"),
    ]
    app = baker.make("api.App")  # noqa:F841
    for item in ip_allow_lists:
        baker.make(
            "api.AppIPAllowList",
            app_id=app.id,
            ip_allowlist_id=item.id,
            deployment_env="test",
        )
    app_ip_ranges = app.env_allowed_ip_ranges("test")
    assert " " not in app_ip_ranges
    assert len(app_ip_ranges.split(",")) == 4

    full_app_ip_ranges = app.app_allowed_ip_ranges
    assert " " not in full_app_ip_ranges
    assert len(full_app_ip_ranges.split(",")) == 4


def test_iam_role_arn():
    app = App(slug="example-app")
    assert (
        app.iam_role_arn == f"arn:aws:iam::{settings.AWS_DATA_ACCOUNT_ID}:role/test_app_example-app"
    )


@pytest.mark.parametrize(
    "namespace, env, expected",
    [
        ("data-platform-app-example", "dev", "example-dev"),
        ("example", "dev", "example-dev"),
        ("data-platform-example", "dev", "data-platform-example-dev"),
        ("data-platform-app-example", "prod", "example"),
        ("example", "prod", "example"),
        ("data-platform-example", "prod", "data-platform-example"),
    ],
)
def test_app_url_name(namespace, env, expected):
    app = App(namespace=namespace)
    assert app.app_url_name(env_name=env) == expected


@pytest.mark.parametrize("env", ["dev", "prod"], ids=["dev", "prod"])
def test_get_logs_url(env):
    expected = (
        "https://app-logs.cloud-platform.service.justice.gov.uk/_dashboards/app/data-explorer/discover#?_a=(discover:"
        "(columns:!(kubernetes.container_name,kubernetes.namespace_name,log),isDirty:!f,sort:!()),metadata:"
        "(indexPattern:bb90f230-0d2e-11ef-bf63-53113938c53a,view:discover))&_g=(filters:!(),refreshInterval:(pause:!t,"
        "value:0),time:(from:now-60m,to:now))&_q=(filters:!(('$state':(store:appState),meta:(alias:!n,disabled:!f,"
        "index:bb90f230-0d2e-11ef-bf63-53113938c53a,key:kubernetes.namespace_name,negate:!f,params:(query:"
        f"example-namespace-{env}),type:phrase),query:(match_phrase:(kubernetes.namespace_name:example-namespace-"
        f"{env}))),('$state':(store:appState),meta:(alias:!n,disabled:!f,index:bb90f230-0d2e-11ef-bf63-53113938c53a,"
        "key:kubernetes.container_name,negate:!f,params:(query:webapp),type:phrase),query:(match_phrase:"
        "(kubernetes.container_name:webapp)))),query:(language:kuery,query:''))"
    )
    app = App(namespace="example-namespace")
    assert app.get_logs_url(env=env) == expected
