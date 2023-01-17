"App permissions tests"

# Standard library
import json
from unittest.mock import patch

# Third-party
import pytest
from django.contrib import auth
from django.contrib.auth import get_user
from model_mommy import mommy
from rest_framework import status
from rest_framework.reverse import reverse
from rules import has_perm, perm_exists

# First-party/Local
import controlpanel.api.rules


@pytest.fixture
def users(users):
    users.update(
        {
            "app_admin": mommy.make(
                "api.User",
                username="dave",
                auth0_id="github|user_4",
            ),
        }
    )
    return users


@pytest.fixture(autouse=True)
def app(users):
    app = mommy.make("api.App", name="Test App 1")
    user = users["app_admin"]
    mommy.make("api.UserApp", user=user, app=app, is_admin=True)
    return app


def app_list(client, *args):
    return client.get(reverse("app-list"))


def app_detail(client, app, *args):
    return client.get(reverse("app-detail", (app.id,)))


def app_delete(client, app, *args):
    return client.delete(reverse("app-detail", (app.id,)))


def app_create(client, *args):
    data = {"name": "test-app", "repo_url": "https://example.com"}
    return client.post(reverse("app-list"), data)


def app_update(client, app, *args):
    data = {"name": "test-app", "repo_url": "https://example.com"}
    return client.put(
        reverse("app-detail", (app.id,)),
        json.dumps(data),
        content_type="application/json",
    )


def test_perm_rules_setup():
    assert perm_exists("api.list_app")


def test_authenticated_user_has_basic_perms(client, users):
    anonymous_user = get_user(client)
    assert not anonymous_user.has_perm("api.list_app")

    assert users["normal_user"].has_perm("api.list_app")


@pytest.mark.parametrize(
    "view,user,expected_status",
    [
        (app_list, "superuser", status.HTTP_200_OK),
        (app_detail, "superuser", status.HTTP_200_OK),
        (app_delete, "superuser", status.HTTP_204_NO_CONTENT),
        (app_create, "superuser", status.HTTP_201_CREATED),
        (app_update, "superuser", status.HTTP_200_OK),
        (app_list, "normal_user", status.HTTP_200_OK),
        (app_detail, "normal_user", status.HTTP_403_FORBIDDEN),
        (app_delete, "normal_user", status.HTTP_403_FORBIDDEN),
        (app_create, "normal_user", status.HTTP_403_FORBIDDEN),
        (app_update, "normal_user", status.HTTP_403_FORBIDDEN),
        (app_list, "app_admin", status.HTTP_200_OK),
        (app_detail, "app_admin", status.HTTP_200_OK),
        (app_delete, "app_admin", status.HTTP_403_FORBIDDEN),
        (app_create, "app_admin", status.HTTP_403_FORBIDDEN),
        (app_update, "app_admin", status.HTTP_403_FORBIDDEN),
    ],
)
@pytest.mark.django_db
def test_permission(client, app, users, view, user, expected_status):
    u = users[user]
    client.force_login(u)

    with patch("controlpanel.api.views.models.App.delete"):
        response = view(client, app)
        assert response.status_code == expected_status
