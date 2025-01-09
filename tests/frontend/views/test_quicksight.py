# Standard library
from unittest.mock import patch

# Third-party
import botocore
import pytest
from django.conf import settings
from django.urls import reverse
from rest_framework import status

# Original botocore _make_api_call function
orig = botocore.client.BaseClient._make_api_call


# Mocked botocore _make_api_call function
def mock_make_api_call(self, operation_name, kwarg):
    op_names = [
        {"GenerateEmbedUrlForRegisteredUser": {}},
    ]

    for operation in op_names:
        if operation_name in operation:
            return operation[operation_name]

    # If we don't want to patch the API call
    return orig(self, operation_name, kwarg)


def quicksight(client):
    return client.get(reverse("quicksight"))


@pytest.mark.parametrize(
    "view,user,expected_status",
    [
        (quicksight, "superuser", status.HTTP_200_OK),
        (quicksight, "database_user", status.HTTP_403_FORBIDDEN),
        (quicksight, "normal_user", status.HTTP_403_FORBIDDEN),
        (quicksight, "quicksight_compute_author", status.HTTP_200_OK),
        (quicksight, "quicksight_compute_reader", status.HTTP_200_OK),
    ],
)
def test_permission(client, users, view, user, expected_status):
    client.force_login(users[user])
    with patch("botocore.client.BaseClient._make_api_call", new=mock_make_api_call):
        response = view(client)
        assert response.status_code == expected_status
