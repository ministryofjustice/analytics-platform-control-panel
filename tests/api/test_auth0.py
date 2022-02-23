from unittest.mock import call, patch

import pytest
from controlpanel.api import auth0


@pytest.fixture
def AuthorizationAPI():
    return auth0.AuthorizationAPI()


@pytest.fixture
def ManagementAPI():
    return auth0.ManagementAPI()


@pytest.yield_fixture
def fixture_users_200(AuthorizationAPI):
    with patch.object(AuthorizationAPI, "request") as request:
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
def fixture_groups(AuthorizationAPI):
    with patch.object(AuthorizationAPI, "request") as request:
        request.side_effect = [
            {
                "total": 2,
                "groups": [
                    {"name": "foo", "_id": "foo-id"},
                    {"name": "bar", "_id": "bar-id"},
                ],
            },
        ]
        yield


def test_list_more_than_100_users(AuthorizationAPI, fixture_users_200):
    users = AuthorizationAPI.get_users()
    assert len(users) == 200


def test_get_group_by_name(AuthorizationAPI, fixture_groups):
    group = AuthorizationAPI.get_group("foo")
    AuthorizationAPI.request.assert_called_with("GET", "groups", params={})
    assert group["name"] == "foo"


def test_get_group_id(AuthorizationAPI, fixture_groups):
    group_id = AuthorizationAPI.get_group_id("foo")
    AuthorizationAPI.request.assert_called_with("GET", "groups", params={})
    assert group_id == "foo-id"


@pytest.yield_fixture
def fixture_get_group(AuthorizationAPI):
    with patch.object(AuthorizationAPI, "get_group") as get_group:
        get_group.return_value = {
            "_id": "foo-id",
            "name": "foo",
            "roles": ["role_1", "role_2"],
        }
        yield get_group


def test_delete_group(AuthorizationAPI, fixture_get_group):
    with patch.object(AuthorizationAPI, "request") as request:
        group_id = "foo-id"
        role_id = "foo-role-id"
        permission_id = "foo-permission-id"

        request.return_value = [
            {"_id": role_id, "permissions": [permission_id]},
        ]

        AuthorizationAPI.delete_group(group_name="foo")

        fixture_get_group.assert_called_with("foo")

        request.assert_has_calls(
            [
                call("GET", f"groups/{group_id}/roles"),
                call("DELETE", f"groups/{group_id}"),
                call("DELETE", f"roles/{role_id}"),
                call("DELETE", f"permissions/{permission_id}"),
            ]
        )


def test_create_user(ManagementAPI):
    with patch.object(ManagementAPI, "request") as request:
        email = "foo@test.com"
        nickname = "foo"
        request.return_value = {
            "email": "foo@test.com",
            "email_verified": True,
            "identities": [
                {
                    "connection": "email",
                    "user_id": "61f9b45470ad3d31400c8cec",
                    "provider": "email",
                    "isSocial": False,
                }
            ],
            "name": "foot@test.com",
            "nickname": "foo",
            "user_id": "email|61f9b45470ad3d31400c8cec",
        }

        ManagementAPI.create_user(email=email, email_verified=True, connection="email")

        request.assert_has_calls(
            [
                call(
                    "POST",
                    "users",
                    json={
                        "email": email,
                        "email_verified": True,
                        "connection": "email",
                        "nickname": nickname,
                    },
                )
            ]
        )


@pytest.yield_fixture
def fixture_get_users_email_search_empty(AuthorizationAPI):
    with patch.object(
        AuthorizationAPI.mgmt, "get_users_email_search"
    ) as get_users_email_search:
        get_users_email_search.return_value = []
        yield get_users_email_search


@pytest.yield_fixture
def fixture_get_users_email_search(AuthorizationAPI):
    with patch.object(
        AuthorizationAPI.mgmt, "get_users_email_search"
    ) as get_users_email_search:
        get_users_email_search.return_value = [
            {
                "email": "new@test.com",
                "email_verified": True,
                "identities": [
                    {
                        "connection": "email",
                        "user_id": "new_id",
                        "provider": "email",
                        "isSocial": False,
                    }
                ],
                "name": "foot@test.com",
                "nickname": "foo",
                "user_id": "email|new_id",
            }
        ]
        yield get_users_email_search


@pytest.yield_fixture
def fixture_create_user(AuthorizationAPI):
    with patch.object(AuthorizationAPI.mgmt, "create_user") as create_user:
        create_user.return_value = {
            "email": "foo@test.com",
            "email_verified": True,
            "identities": [
                {
                    "connection": "email",
                    "user_id": "new_id",
                    "provider": "email",
                    "isSocial": False,
                }
            ],
            "name": "foot@test.com",
            "nickname": "foo",
            "user_id": "email|new_id",
        }
        yield create_user



def test_new_user_add_to_group(
    AuthorizationAPI,
    fixture_groups,
    fixture_get_group,
    fixture_get_users_email_search_empty,
    fixture_create_user,
):
    with patch.object(AuthorizationAPI, "request") as auth_request:
        group_id = "foo-id"
        group_name = "foo"
        email = "new@test.com"
        nickname = "new"
        new_id = "new_id"

        response = AuthorizationAPI.add_group_members(
            emails=[email], group_name="foo", user_options={"connection": "email"}
        )

        auth_request.assert_has_calls(
            [call("PATCH", f"groups/{group_id}/members", json=[f"email|{new_id}"])]
        )


def test_existing_user_add_to_group(AuthorizationAPI,
                               fixture_groups,
                               fixture_get_group,
                               fixture_get_users_email_search,
                               fixture_create_user
                               ):
    with patch.object(AuthorizationAPI, "request") as auth_request:
        group_id = "foo-id"
        group_name = "foo"
        email = "New@test.com"
        nickname = "new"
        new_id = "new_id"

        response = AuthorizationAPI.add_group_members(
            emails=[email], group_name="foo", user_options={"connection": "email"}
        )

        auth_request.assert_has_calls([
            call('PATCH', f'groups/{group_id}/members', json=[f'email|{new_id}'])
        ])
