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


def quicksight(client):
    return client.get(reverse("quicksight"))


@pytest.mark.parametrize(
    "view,user,expected_status",
    [
        (quicksight, "superuser", status.HTTP_200_OK),
        (quicksight, "database_user", status.HTTP_403_FORBIDDEN),
        (quicksight, "normal_user", status.HTTP_403_FORBIDDEN),
        (quicksight, "quicksight_author_user", status.HTTP_200_OK),
        (quicksight, "quicksight_reader_user", status.HTTP_200_OK),
    ],
)
def test_permission(client, users, view, user, expected_status):
    client.force_login(users[user])
    response = view(client)
    assert response.status_code == expected_status
