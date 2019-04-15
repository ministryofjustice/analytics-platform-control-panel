from unittest.mock import patch

from model_mommy import mommy
import pytest

from controlpanel.api.models import App
from tests.api import APP_IAM_ROLE_ASSUME_POLICY


@pytest.yield_fixture
def aws():
    with patch("controlpanel.api.services.aws") as aws:
        yield aws


@pytest.yield_fixture
def auth0():
    with patch("controlpanel.api.models.auth0") as auth0:
        yield auth0


@pytest.mark.django_db
def test_slug_characters_replaced():
    repo_url = "https://example.com/foo__bar-baz!bat-1337"
    app = App.objects.create(repo_url=repo_url)
    assert "foo-bar-bazbat-1337" == app.slug


@pytest.mark.django_db
def test_slug_collisions_increments():
    app = App.objects.create(repo_url="git@github.com:org/foo-bar.git")
    assert "foo-bar" == app.slug

    app2 = App.objects.create(repo_url="https://www.example.com/org/foo-bar")
    assert "foo-bar-2" == app2.slug


@pytest.mark.django_db
def test_aws_create_role_calls_service(aws):
    app = App.objects.create(repo_url="https://example.com/repo_name")

    app.aws_create_role()

    aws.create_role.assert_called_with(
        app.iam_role_name,
        APP_IAM_ROLE_ASSUME_POLICY,
    )


@pytest.mark.django_db
def test_aws_delete_role_calls_service(aws):
    app = App.objects.create(repo_url="https://example.com/repo_name")

    app.aws_delete_role()

    aws.delete_role.assert_called_with(app.iam_role_name)


@pytest.mark.django_db
def test_get_customers(auth0):
    app = App.objects.create(repo_url="https://example.com/repo_name")
    authz = auth0.AuthorizationAPI.return_value
    authz.get_group_members.return_value = [
        {"email": "test@example.com"}
    ]

    customers = app.customers

    expected_emails = ["test@example.com"]
    assert expected_emails == [customer["email"] for customer in customers]


@pytest.mark.django_db
def test_add_customers(auth0):
    app = App.objects.create(repo_url="https://example.com/repo_name")
    authz = auth0.AuthorizationAPI.return_value
    emails = ["test1@example.com", "test2@example.com"]

    app.add_customers(emails)

    authz.add_group_members.assert_called_with(
        group_name=app.slug,
        emails=emails,
        user_options={"connection": "email"},
    )


@pytest.mark.django_db
def test_delete_customers(auth0):
    app = App.objects.create(repo_url="https://example.com/repo_name")
    authz = auth0.AuthorizationAPI.return_value

    app.delete_customers(["email|123"])

    authz.delete_group_members.assert_called_with(
        group_name=app.slug,
        user_ids=["email|123"],
    )


@pytest.mark.parametrize('url, expected_name', [
    ('https://github.com/org/a_repo_name', 'a_repo_name'),
    ('git@github.com:org/repo_2.git', 'repo_2'),
    ('https://github.com/org/a_repo_name.git/', 'a_repo_name'),
    ('https://github.com/org/a_repo_name/', 'a_repo_name'),
    ('http://foo.com', 'foo.com'),
    ('http://foo.com/', 'foo.com'),
])
def test_repo_name(url, expected_name):
    app = mommy.prepare('api.App')
    app.repo_url = url
    assert app._repo_name == expected_name
