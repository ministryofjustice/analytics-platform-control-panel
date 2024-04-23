"App permissions tests"

# Standard library
import json
from unittest.mock import patch

# Third-party
import pytest
from django.contrib.auth import get_user
from model_bakery import baker
from rest_framework import status
from rest_framework.reverse import reverse
from rules import perm_exists


@pytest.fixture
def users(users):
    users.update(
        {
            "app_admin": baker.make(
                "api.User",
                username="dave",
                auth0_id="github|user_4",
            ),
            "app_user": baker.make(
                "api.User",
                username="testing",
                auth0_id="github|user_5",
            ),
        }
    )
    return users


@pytest.fixture(autouse=True)
def app(users):
    app = baker.make("api.App", name="Test App 1")
    user = users["app_admin"]
    baker.make("api.UserApp", user=user, app=app, is_admin=True)

    user = users["app_user"]
    baker.make("api.UserApp", user=user, app=app, is_admin=False)
    return app


@pytest.fixture  # noqa: F405
def authz():
    with patch("controlpanel.api.auth0.ExtendedAuth0") as authz:
        yield authz()


def app_list(client, *args):
    return client.get(reverse("app-list"))


def app_detail(client, app, *args):
    return client.get(reverse("app-detail", (app.res_id,)))


def app_delete(client, app, *args):
    return client.delete(reverse("app-detail", (app.res_id,)))


def app_create(client, *args):
    data = {"name": "test-app", "repo_url": "https://github.com/ministryofjustice/example"}
    return client.post(reverse("app-list"), data)


def app_update(client, app, *args):
    data = {"name": "test-app", "repo_url": "https://github.com/ministryofjustice/example"}
    return client.put(
        reverse("app-detail", (app.res_id,)),
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
        (app_detail, "app_user", status.HTTP_403_FORBIDDEN),
        (app_detail, "normal_user", status.HTTP_404_NOT_FOUND),
        (app_delete, "normal_user", status.HTTP_403_FORBIDDEN),
        (app_create, "normal_user", status.HTTP_201_CREATED),
        (app_update, "normal_user", status.HTTP_404_NOT_FOUND),
        (app_list, "app_admin", status.HTTP_200_OK),
        (app_detail, "app_admin", status.HTTP_200_OK),
        (app_delete, "app_admin", status.HTTP_403_FORBIDDEN),
        (app_create, "app_admin", status.HTTP_201_CREATED),
        (app_update, "app_admin", status.HTTP_200_OK),
    ],
)
@pytest.mark.django_db
def test_permission(client, app, users, view, user, expected_status, authz):
    u = users[user]
    client.force_login(u)

    with patch("controlpanel.api.views.models.App.delete"):
        response = view(client, app)
        assert response.status_code == expected_status


def apps_by_name_detail(client, app, *args):
    return client.get(reverse("apps-by-name-detail", (app.name,)))


@pytest.mark.parametrize(
    "view,user,expected_status",
    [
        (apps_by_name_detail, "superuser", status.HTTP_200_OK),
        (apps_by_name_detail, "app_user", status.HTTP_403_FORBIDDEN),
        (apps_by_name_detail, "normal_user", status.HTTP_403_FORBIDDEN),
        (apps_by_name_detail, "app_admin", status.HTTP_200_OK),
    ],
)
@pytest.mark.django_db
def test_apps_by_name_permission(client, app, users, view, user, expected_status):
    u = users[user]
    client.force_login(u)

    response = view(client, app)
    assert response.status_code == expected_status
