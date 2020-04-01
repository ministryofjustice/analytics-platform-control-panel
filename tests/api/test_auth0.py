from unittest.mock import patch

import pytest

from controlpanel.api import auth0


@pytest.fixture
def AuthorizationAPI():
    return auth0.AuthorizationAPI()


@pytest.yield_fixture
def users_200(AuthorizationAPI):
    with patch.object(AuthorizationAPI, 'request') as request:
        request.side_effect = [
            {
                "total": 200,
                "users": [
                    {
                        "name": f"Test User {(i * 100) + j}",
                        "email": f"test{(i * 100) + j}@example.com",
                        "user_id": f"github|{(i * 100) + j}",
                    }
                    for j in range(100)
                ],
            }
            for i in range(2)
        ]
        yield


@pytest.yield_fixture
def groups(AuthorizationAPI):
    with patch.object(AuthorizationAPI, 'request') as request:
        request.side_effect = [
            {
                "total": 2,
                "groups": [
                    {"name": "foo"},
                    {"name": "bar"},
                ],
            },
        ]
        yield


def test_list_more_than_100_users(AuthorizationAPI, users_200):
    users = AuthorizationAPI.get_users()
    assert len(users) == 200


def test_get_group_by_name(AuthorizationAPI, groups):
    group = AuthorizationAPI.get_group("foo")
    AuthorizationAPI.request.assert_called_with("GET", "groups", params={})
    assert group["name"] == "foo"

def test_get_group_id(AuthorizationAPI, groups):
    group = AuthorizationAPI.get_group("foo")
    AuthorizationAPI.request.assert_called_with("GET", "groups", params={})
    assert group["name"] == "foo"

@pytest.yield_fixture
def get_group(AuthorizationAPI):
    with patch.object(AuthorizationAPI, "get_group") as get_group:
        get_group.return_value = {
            "_id": "foo_id",
            "name": "foo",
            "roles": ["role_1", "role_2"],
        }
        yield get_group


@pytest.yield_fixture
def _delete_group_roles(AuthorizationAPI):
    with patch.object(AuthorizationAPI, "_delete_group_roles") as _delete_group_roles:
        yield _delete_group_roles


def test_delete_group(AuthorizationAPI, get_group, _delete_group_roles):
    with patch.object(AuthorizationAPI, "request") as request:
        AuthorizationAPI.delete_group(group_name="foo")

        get_group.assert_called_with("foo")
        _delete_group_roles.assert_called_with("foo_id", ["role_1", "role_2"])
        request.assert_called_with("DELETE", f"groups/foo_id")

def test_delete_group_roles(AuthorizationAPI):
    with patch.object(AuthorizationAPI, "request") as request:
        group_id = "group_id_1"
        role_ids = ["role_id_1", "role_id_2"]
        AuthorizationAPI._delete_group_roles(group_id, role_ids)

        request.assert_called_with(
            "DELETE",
            f"groups/{group_id}/roles",
            json=role_ids,
        )
