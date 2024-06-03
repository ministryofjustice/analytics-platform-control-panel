# Standard library
import json
from unittest.mock import patch

# Third-party
import pytest
from django.conf import settings
from django.urls import reverse
from rest_framework import status


def database_list(client):
    return client.get(reverse("list-databases"))


def list_tables(client):
    kwargs = {"dbname": settings.DPR_DATABASE_NAME}
    return client.get(reverse("list-tables", kwargs=kwargs))


def grant_permissions(client):
    kwargs = {"dbname": settings.DPR_DATABASE_NAME, "tablename": "test_table"}
    form_data = {"entity_id": "github|user_2", "access_level": "readonly"}
    return client.post(reverse("grant-table-permissions", kwargs=kwargs), data=form_data)


def revoke_permissions(client):
    kwargs = {
        "dbname": settings.DPR_DATABASE_NAME,
        "tablename": "test_table",
        "user": "carol",
    }
    return client.post(reverse("revoke-table-permissions", kwargs=kwargs))


@pytest.mark.parametrize(
    "view,user,expected_status",
    [
        (database_list, "superuser", status.HTTP_200_OK),
        (database_list, "database_user", status.HTTP_200_OK),
        (database_list, "normal_user", status.HTTP_403_FORBIDDEN),
        (list_tables, "superuser", status.HTTP_200_OK),
        (list_tables, "database_user", status.HTTP_200_OK),
        (list_tables, "normal_user", status.HTTP_403_FORBIDDEN),
        (grant_permissions, "superuser", status.HTTP_302_FOUND),
        (grant_permissions, "database_user", status.HTTP_302_FOUND),
        (grant_permissions, "normal_user", status.HTTP_403_FORBIDDEN),
        (revoke_permissions, "superuser", status.HTTP_302_FOUND),
        (revoke_permissions, "database_user", status.HTTP_302_FOUND),
        (revoke_permissions, "normal_user", status.HTTP_403_FORBIDDEN),
    ],
)
def test_permission(client, users, view, user, expected_status):
    for key, val in users.items():
        client.force_login(val)
    client.force_login(users[user])
    response = view(client)
    assert response.status_code == expected_status
