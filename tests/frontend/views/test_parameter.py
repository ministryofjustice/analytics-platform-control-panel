# Standard library
from unittest.mock import patch

# Third-party
import pytest
from django.urls import reverse
from model_mommy import mommy
from rest_framework import status

NUM_APPS = 3


@pytest.fixture(autouse=True)
def users(users):
    users.update(
        {
            "owner": mommy.make("api.User", username="owner"),
        }
    )
    return users


@pytest.fixture(autouse=True)
def app(users):
    mommy.make("api.App", NUM_APPS - 1)
    app = mommy.make("api.App")
    mommy.make("api.UserApp", user=users["superuser"], app=app, is_admin=True)
    return app


def list(client, *args):
    return client.get(reverse("list-parameters"))


def list_all(client, *args):
    return client.get(reverse("list-all-parameters"))


def create(client, app, data_dict, *args, **kwargs):
    data = {"app_id": app.id}
    data = {**data, **data_dict}
    return client.post(reverse("create-parameter", kwargs=dict(app_id=app.id)), data)


def delete(client, app, param, *args):
    key = param.get("key")
    return client.get(reverse("delete-parameter"), dict(key=key, app_id=app.id))


@pytest.yield_fixture
def fixture_create_update_secret():
    with patch(
        "controlpanel.api.aws.AWSSecretManager.create_or_update"
    ) as create_or_update:
        yield create_or_update


@pytest.mark.parametrize(
    "view,user,expected_status,data_input",
    [
        (
            create,
            "superuser",
            status.HTTP_302_FOUND,
            dict(key="environment", value="prod"),
        ),
        (create, "owner", status.HTTP_200_OK, {}),
        (create, "normal_user", status.HTTP_200_OK, {}),
        (delete, "superuser", status.HTTP_302_FOUND, dict(key="hello")),
        (delete, "owner", status.HTTP_302_FOUND, dict(key="hello")),
        (delete, "normal_user", status.HTTP_302_FOUND, dict(key="hello")),
    ],
)
def test_permission(
    client,
    app,
    users,
    fixture_create_update_secret,
    view,
    user,
    expected_status,
    data_input,
):
    client.force_login(users[user])
    response = view(client, app, data_input)
    assert response.status_code == expected_status
    assert fixture_create_update_secret.called_once()
    if data_input:
        assert fixture_create_update_secret.called_once_with(data_input)
