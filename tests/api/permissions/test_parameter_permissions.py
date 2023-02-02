# Standard library
import json
from unittest.mock import patch

# Third-party
import pytest
from model_mommy import mommy
from rest_framework import status
from rest_framework.reverse import reverse


@pytest.fixture
def users(users):
    users.update(
        {
            "parameter_owner": mommy.make("api.User", username="parameter_owner"),
        }
    )
    return users


@pytest.fixture
def parameter(users):
    with patch("controlpanel.api.aws.AWSParameterStore.create_parameter"):
        return mommy.make("api.Parameter", created_by=users["parameter_owner"])


def list(client, *args):
    return client.get(reverse("parameter-list"))


def create(client, *args):
    data = {
        "key": "test_key_1",
        "description": "test_description",
        "app_type": "webapp",
        "role_name": "test_role_name",
        "value": "test_value",
    }
    return client.post(
        reverse("parameter-list"),
        json.dumps(data),
        content_type="application/json",
    )


def retrieve(client, parameter, *args):
    return client.get(reverse("parameter-detail", (parameter.id,)))


def update(client, parameter, *args):
    data = {
        "key": "test_key_1",
        "description": "test_description",
        "app_type": "webapp",
        "value": "test_value",
        "role_name": "other_role_name",
    }
    return client.put(
        reverse("parameter-detail", (parameter.id,)),
        json.dumps(data),
        content_type="application/json",
    )


def delete(client, parameter, *args):
    return client.delete(reverse("parameter-detail", (parameter.id,)))


@pytest.mark.parametrize(
    "view,user,expected_status",
    [
        (list, "superuser", status.HTTP_200_OK),
        (create, "superuser", status.HTTP_201_CREATED),
        (retrieve, "superuser", status.HTTP_200_OK),
        (update, "superuser", status.HTTP_200_OK),
        (delete, "superuser", status.HTTP_204_NO_CONTENT),
        (list, "normal_user", status.HTTP_200_OK),
        (create, "normal_user", status.HTTP_201_CREATED),
        (retrieve, "normal_user", status.HTTP_404_NOT_FOUND),
        (update, "normal_user", status.HTTP_404_NOT_FOUND),
        (delete, "normal_user", status.HTTP_404_NOT_FOUND),
        (list, "parameter_owner", status.HTTP_200_OK),
        (create, "parameter_owner", status.HTTP_201_CREATED),
        (retrieve, "parameter_owner", status.HTTP_200_OK),
        (update, "parameter_owner", status.HTTP_200_OK),
        (delete, "parameter_owner", status.HTTP_204_NO_CONTENT),
    ],
)
@pytest.mark.django_db
def test_permission(client, parameter, users, view, user, expected_status):
    with patch("controlpanel.api.aws.AWSParameterStore.create_parameter"):
        if user:
            client.force_login(users[user])
        response = view(client, parameter)
        assert response.status_code == expected_status
