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
    mommy.make("api.UserApp", user=users["owner"], app=app, is_admin=True)
    return app


def create(client, app, data_dict, *args, **kwargs):
    data = {"app_id": app.id}
    data = {**data, **data_dict}
    return client.post(reverse("create-app-var", kwargs={"pk": app.id}), data)


def delete(client, app, param, *args):
    key = param.get("key")
    return client.post(reverse("delete-app-var", kwargs={"pk": app.id, "var_name": key}))


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


@pytest.fixture
def fixture_create_update_var():
    with patch(
        "controlpanel.api.cluster.App.create_or_update_env_var"
    ) as create_or_update:
        yield create_or_update


@pytest.fixture
def fixture_delete_var():
    with patch(
        "controlpanel.api.cluster.App.delete_env_var"
    ) as delete_env_var:
        yield delete_env_var


@pytest.mark.parametrize(
    "view,user,expected_status,data_input,create_call_count,delete_call_count,expected_data",
    [
        (
            create,
            "superuser",
            status.HTTP_302_FOUND,
            dict(key="environment", value="prod", env_name="test_env"),
            1,
            0,
            dict(env_name="test_env", key_name="XXX_environment", key_value="prod"),
        ),
        (create, "owner", status.HTTP_200_OK, {}, 0, 0, None),
        (create, "normal_user", status.HTTP_200_OK, {}, 0, 0, None),
        (delete, "superuser", status.HTTP_302_FOUND, dict(key="hello"), 0, 1, None),
        (delete, "owner", status.HTTP_302_FOUND, dict(key="hello"), 0, 1, None),
        (delete, "normal_user", status.HTTP_403_FORBIDDEN, dict(key="hello"), 0, 0, None),
    ],
)
def test_permission(
    client,
    app,
    users,
    view,
    user,
    expected_status,
    data_input,
    fixture_create_update_var,
    fixture_delete_var,
    create_call_count,
    delete_call_count,
    expected_data
):
    client.force_login(users[user])
    response = view(client, app, data_input)
    assert response.status_code == expected_status
    assert fixture_create_update_var.call_count == create_call_count
    assert fixture_delete_var.call_count == delete_call_count
    if data_input and create_call_count == 1:
        fixture_create_update_var.assert_called_once_with(**expected_data)
