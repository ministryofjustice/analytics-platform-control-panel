# Standard library
from unittest.mock import patch

# Third-party
import pytest
from django.urls import reverse
from model_mommy import mommy
from pydantic import parse_obj_as
from rest_framework import status

# First-party/Local
from controlpanel.api.serializers import SecretSerializer

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
def test_permission(client, app, users, view, user, expected_status, data_input):
    client.force_login(users[user])
    response = view(client, app, data_input)
    assert response.status_code == expected_status


@pytest.yield_fixture
def fixture_create_update_secret():
    with patch(
        "controlpanel.api.aws.AWSSecretManager.create_or_update"
    ) as create_or_update:
        yield create_or_update


@pytest.mark.parametrize(
    "data_input,change,valid_after,out",
    [
        (dict(environ="alpha"), {}, [], dict(environ="alpha")),
        (
            dict(environ="alpha"),
            dict(prod="True"),
            [],
            dict(environ="alpha", prod="True"),
        ),
        (dict(environ="alpha"), {"bad#-key": "value"}, [1], None),
        (
            dict(environ="alpha", complex="True"),
            {"extra_key": "value"},
            [],
            dict(environ="alpha", complex="True", extra_key="value"),
        ),
        (dict(), {"extra_key": "value"}, [], dict(extra_key="value")),
    ],
)
def test_add_parameter_serializer(data_input, change, valid_after, out):
    serial = parse_obj_as(SecretSerializer, data_input)
    errors = []
    for key, value in change.items():
        serial, error = serial.update_item(key, value)
        if error:
            errors.append(error)

    assert len(valid_after) == len(errors)
    if out:
        assert serial.get_data() == out
