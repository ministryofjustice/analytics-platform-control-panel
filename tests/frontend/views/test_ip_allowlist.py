# Third-party
import pytest
from model_mommy import mommy
from rest_framework import status
from rest_framework.reverse import reverse


@pytest.fixture(autouse=True)
def ip_allowlist():
    allowlist = mommy.make(
        "api.IPAllowlist",
        name="Test IP allowlist 1",
        allowed_ip_ranges="192.168.0.0/28",
    )
    return allowlist


def ip_allowlist_list(client, *args):
    return client.get(reverse("list-ip-allowlists"))


def ip_allowlist_create(client, *args):
    return client.get(reverse("create-ip-allowlist"))


def ip_allowlist_delete(client, ip_allowlist, *args):
    return client.post(reverse("delete-ip-allowlist", (ip_allowlist.id,)))


def ip_allowlist_detail(client, ip_allowlist, *args):
    return client.get(reverse("manage-ip-allowlist", (ip_allowlist.id,)))


@pytest.mark.parametrize(
    "view, user, expected_status",
    [
        (ip_allowlist_list, "superuser", status.HTTP_200_OK),
        (ip_allowlist_detail, "superuser", status.HTTP_200_OK),
        (ip_allowlist_delete, "superuser", status.HTTP_302_FOUND),
        (ip_allowlist_create, "superuser", status.HTTP_200_OK),
        (ip_allowlist_list, "normal_user", status.HTTP_403_FORBIDDEN),
        (ip_allowlist_detail, "normal_user", status.HTTP_403_FORBIDDEN),
        (ip_allowlist_delete, "normal_user", status.HTTP_403_FORBIDDEN),
        (ip_allowlist_create, "normal_user", status.HTTP_403_FORBIDDEN),
    ],
)
@pytest.mark.django_db
def test_permission(client, ip_allowlist, users, view, user, expected_status):
    client.force_login(users[user])
    response = view(client, ip_allowlist)
    assert response.status_code == expected_status
