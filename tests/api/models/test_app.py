from unittest.mock import patch

from model_mommy import mommy
import pytest

from controlpanel.api.models import App
from tests.api.fixtures.aws import *


@pytest.yield_fixture
def auth0():
    with patch("controlpanel.api.models.app.auth0") as auth0:
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
    aws.create_app_role.assert_called_with(app)


@pytest.mark.django_db
def test_delete_also_deletes_app_artifacts(auth0, secretsmanager):
    app = App.objects.create(repo_url="https://example.com/repo_name")
    authz = auth0.ExtendedAuth0.return_value
    with patch("controlpanel.api.models.app.cluster") as cluster:
        app.delete()

        cluster.App.assert_called_with(app)
        cluster.App.return_value.delete.assert_called()
        authz.clear_up_app.assert_called_with(app_name=app.slug, group_name=app.slug)


@pytest.mark.django_db
def test_get_customers(auth0):
    app = App.objects.create(repo_url="https://example.com/repo_name")
    authz = auth0.ExtendedAuth0.return_value
    authz.groups.get_group_members.return_value = [
        {"email": "test@example.com"}
    ]

    customers = app.customers

    expected_emails = ["test@example.com"]
    assert expected_emails == [customer["email"] for customer in customers]


@pytest.mark.django_db
def test_add_customers(auth0):
    app = App.objects.create(repo_url="https://example.com/repo_name")
    authz = auth0.ExtendedAuth0.return_value
    emails = ["test1@example.com", "test2@example.com"]

    app.add_customers(emails)

    authz.add_group_members_by_emails.assert_called_with(
        group_name=app.slug,
        emails=emails,
        user_options={"connection": "email"},
    )


@pytest.mark.django_db
def test_delete_customers(auth0):
    app = App.objects.create(repo_url="https://example.com/repo_name")
    authz = auth0.ExtendedAuth0.return_value

    app.delete_customers(["email|123"])

    authz.groups.delete_group_members.assert_called_with(
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
