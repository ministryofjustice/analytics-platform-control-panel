# Standard library
import json
from unittest.mock import call, patch, ANY

# Third-party
import pytest
from django.conf import settings
from auth0 import exceptions

# First-party/Local
from controlpanel.api import auth0


@pytest.fixture()
def ExtendedAuth0():
    with patch(
        "auth0.authentication.GetToken.client_credentials"
    ) as client_credentials:
        client_credentials.return_value = {"access_token": "access_token_testing"}
        yield auth0.ExtendedAuth0()


@pytest.fixture
def fixture_users_200(ExtendedAuth0):
    with patch.object(ExtendedAuth0.users, "all") as request:
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


@pytest.fixture
def fixture_users_create(ExtendedAuth0):
    with patch.object(ExtendedAuth0.users, "create") as request:
        request.side_effect = [{"name": "create-testing-bob"}]
        yield


def test_get_all_with_more_than_100(ExtendedAuth0, fixture_users_200):
    users = ExtendedAuth0.users.get_all()
    assert len(users) == 200


def test_search_first_match_by_name_exist(ExtendedAuth0, fixture_users_200):
    user = ExtendedAuth0.users.search_first_match(dict(name="Test User 1"))
    assert user["name"] == "Test User 1"


def test_search_first_match_by_name_not(ExtendedAuth0, fixture_users_200):
    user = ExtendedAuth0.users.search_first_match(dict(name="Different User"))
    assert user is None


def test_get_or_create_new(ExtendedAuth0, fixture_users_200, fixture_users_create):
    user = ExtendedAuth0.users.get_or_create(dict(name="bob"))
    assert user["name"] == "create-testing-bob"


def test_get_or_create_existed(ExtendedAuth0, fixture_users_200, fixture_users_create):
    user = ExtendedAuth0.users.search_first_match(dict(name="Test User 1"))
    assert user["name"] == "Test User 1"


@pytest.fixture
def fixture_has_group_existed(ExtendedAuth0):
    with patch.object(ExtendedAuth0.groups, "has_group_existed") as has_group_existed:
        has_group_existed.return_value = True
        yield has_group_existed


@pytest.fixture
def fixture_get_group_roles(ExtendedAuth0):
    with patch.object(ExtendedAuth0.groups, "all") as groups_all:
        groups_all.return_value = [
            {"name": "role1", "_id": "role1", "permissions": ["permission1"]},
            {"name": "role2", "_id": "role2", "permissions": ["permission2"]},
        ]
        yield groups_all


@pytest.fixture
def fixture_roles_delete(ExtendedAuth0):
    with patch.object(ExtendedAuth0.roles, "delete") as roles_delete:
        roles_delete.return_value = []
        yield roles_delete


@pytest.fixture
def fixture_permission_delete(ExtendedAuth0):
    with patch.object(ExtendedAuth0.permissions, "delete") as permissions_delete:
        permissions_delete.return_value = []
        yield permissions_delete


@pytest.fixture
def fixture_groups_delete(ExtendedAuth0):
    with patch.object(ExtendedAuth0.groups, "delete") as groups_delete:
        groups_delete.return_value = []
        yield groups_delete


def test_clear_up_group(
    ExtendedAuth0,
    fixture_has_group_existed,
    fixture_get_group_roles,
    fixture_roles_delete,
    fixture_permission_delete,
    fixture_groups_delete,
):

    ExtendedAuth0.clear_up_group(group_id="foo-id")

    fixture_groups_delete.assert_called_with("foo-id")
    fixture_roles_delete.assert_has_calls([call("role1"), call("role2")])
    fixture_permission_delete.assert_has_calls(
        [call("permission1"), call("permission2")]
    )


def test_create_user(ExtendedAuth0):
    with patch.object(ExtendedAuth0.users, "create") as request:
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

        ExtendedAuth0.users.create_user(
            email=email, email_verified=True, connection="email"
        )

        request.assert_has_calls(
            [
                call(
                    {
                        "email": email,
                        "email_verified": True,
                        "connection": "email",
                        "nickname": nickname,
                    },
                )
            ]
        )


@pytest.fixture
def fixture_get_users_email_search_empty(ExtendedAuth0):
    with patch.object(
        ExtendedAuth0.users, "get_users_email_search"
    ) as get_users_email_search:
        get_users_email_search.return_value = []
        yield get_users_email_search


@pytest.fixture
def fixture_get_users_email_search(ExtendedAuth0):
    with patch.object(
        ExtendedAuth0.users, "get_users_email_search"
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
                "user_id": "email|existing_id",
            }
        ]
        yield get_users_email_search


@pytest.fixture
def fixture_create_user(ExtendedAuth0):
    with patch.object(ExtendedAuth0.users, "create_user") as create_user:
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


@pytest.fixture
def fixture_groups_update(ExtendedAuth0):
    with patch.object(ExtendedAuth0.groups.client, "patch") as group_update:
        group_update.return_value = {}
        yield group_update


def test_new_user_add_to_group(
    ExtendedAuth0,
    fixture_get_users_email_search_empty,
    fixture_create_user,
    fixture_groups_update,
):
    group_id = "foo-id-1"
    email = "new@test.com"
    ExtendedAuth0.add_group_members_by_emails(
        emails=[email], group_id=group_id, user_options={"connection": "email"}
    )
    domain = settings.AUTH0["authorization_extension_url"]
    fixture_groups_update.assert_has_calls(
        [call(f"{domain}/groups/{group_id}/members", data=["email|new_id"])]
    )


def test_existing_user_add_to_group(
    ExtendedAuth0,
    fixture_get_users_email_search,
    fixture_create_user,
    fixture_groups_update,
):
    group_id = "foo-id-1"
    email = "New@test.com"

    ExtendedAuth0.add_group_members_by_emails(
        emails=[email], group_id=group_id, user_options={"connection": "email"}
    )
    domain = settings.AUTH0["authorization_extension_url"]
    fixture_groups_update.assert_has_calls(
        [call(f"{domain}/groups/{group_id}/members", data=["email|existing_id"])]
    )


@pytest.fixture
def fixture_client_create(ExtendedAuth0):
    with patch.object(ExtendedAuth0.clients, "create") as client_create:
        client_create.return_value = {
            "client_id": "new_client_id",
            "name": "new_client",
        }
        yield client_create


@pytest.fixture
def fixture_connection_search_first_match(ExtendedAuth0):
    with patch.object(
        ExtendedAuth0.connections, "search_first_match"
    ) as connection_search_first_match:
        connection_search_first_match.return_value = {
            "name": "email",
            "id": "con_0000000000000001",
        }
        yield connection_search_first_match


@pytest.fixture
def fixture_connection_disable_client(ExtendedAuth0):
    with patch.object(
        ExtendedAuth0.connections, "disable_client"
    ) as connection_disable_client:
        connection_disable_client.return_value = {}
        yield connection_disable_client


@pytest.fixture
def fixture_connection_enable_client(ExtendedAuth0):
    with patch.object(
        ExtendedAuth0.connections, "enable_client"
    ) as connection_enable_client:
        connection_enable_client.return_value = {}
        yield connection_enable_client


@pytest.fixture
def fixture_connection_get_all(ExtendedAuth0):
    with patch.object(ExtendedAuth0.connections, "get_all") as connection_get_all:
        connection_get_all.return_value = [
            {
                "name": "email",
                "id": "con_0000000000000001",
                "enabled_clients": ["new_client_id"],
            },
            {
                "name": "connection 1",
                "id": "con_0000000000000002",
                "enabled_clients": ["new_client_id"],
            },
            {
                "name": "connection 2",
                "id": "con_0000000000000003",
                "enabled_clients": ["new_client_id"],
            },
        ]
        yield connection_get_all


@pytest.fixture
def fixture_permission_create(ExtendedAuth0):
    with patch.object(ExtendedAuth0.permissions, "create") as permission_create:
        permission_create.return_value = {
            "name": "view:app",
            "_id": "permission_001",
            "applicationId": "new_client_id",
        }
        yield permission_create


@pytest.fixture
def fixture_role_create(ExtendedAuth0):
    with patch.object(ExtendedAuth0.roles, "create") as role_create:
        role_create.return_value = {
            "name": "app-viewer",
            "_id": "role_001",
            "description": "description",
            "applicationType": "client",
            "applicationId": "new_client_id",
        }
        yield role_create


@pytest.fixture
def fixture_group_create(ExtendedAuth0):
    with patch.object(ExtendedAuth0.groups, "create") as group_create:
        group_create.return_value = {"name": "view:app", "_id": "group_001"}
        yield group_create


@pytest.fixture
def fixture_role_add_permission(ExtendedAuth0):
    with patch.object(ExtendedAuth0.roles, "put") as role_add_permission:
        role_add_permission.return_value = {}
        yield role_add_permission


@pytest.fixture
def fixture_group_add_role(ExtendedAuth0):
    with patch.object(ExtendedAuth0.groups.client, "patch") as group_add_role:
        group_add_role.return_value = {}
        yield group_add_role


def test_setup_auth0_client(
    ExtendedAuth0,
    fixture_client_create,
    fixture_connection_disable_client,
    fixture_connection_enable_client,
    fixture_connection_search_first_match,
    fixture_connection_get_all,
    fixture_permission_create,
    fixture_role_create,
    fixture_group_create,
    fixture_role_add_permission,
    fixture_group_add_role,
):

    new_client_name = "new_client"
    new_client_id = "new_client_id"
    app_url = "https://{}.{}".format(new_client_name, ExtendedAuth0.app_domain)
    connection1 = {
        "name": "connection 1",
        "id": "con_0000000000000002",
        "enabled_clients": ["new_client_id"],
    }
    connection2 = {
        "name": "connection 2",
        "id": "con_0000000000000003",
        "enabled_clients": ["new_client_id"],
    }

    ExtendedAuth0.setup_auth0_client(client_name=new_client_name)

    fixture_permission_create.assert_called_with(
        dict(name="view:app", applicationId=new_client_id)
    )
    fixture_role_create.assert_called_with(
        dict(name="app-viewer", applicationId=new_client_id)
    )
    fixture_group_create.assert_called_with(dict(name=new_client_name))

    fixture_role_add_permission.assert_called_with(
        "role_001",
        body={
            "name": "app-viewer",
            "description": "description",
            "applicationId": "new_client_id",
            "applicationType": "client",
            "permissions": ["permission_001"],
        },
    )
    domain = settings.AUTH0["authorization_extension_url"]
    fixture_group_add_role.assert_called_with(
        f"{domain}/groups/group_001/roles", data=["role_001"]
    )


@pytest.fixture
def fixture_users_get_user_groups(ExtendedAuth0):
    with patch.object(ExtendedAuth0.users, "get_user_groups") as get_user_groups:
        get_user_groups.return_value = [
            {
                "_id": "2a1e2b9f-3435-4954-8c5d-56e8e9ce763f",
                "name": "Test",
                "description": "Test",
            },
            {
                "_id": "81097bea-f7a3-48b6-a3fc-e2c3eb6c1ace",
                "name": "Google",
                "description": "Google",
            },
        ]
        yield get_user_groups


@pytest.fixture
def fixture_group_delete_member(ExtendedAuth0):
    with patch.object(ExtendedAuth0.groups.client, "delete") as group_delete_member:
        group_delete_member.return_value = {}
        yield group_delete_member


@pytest.fixture
def fixture_user_delete(ExtendedAuth0):
    with patch.object(ExtendedAuth0.users.client, "delete") as user_delete:
        user_delete.return_value = {}
        yield user_delete


@pytest.fixture
def fixture_user_has_existed(ExtendedAuth0):
    with patch.object(ExtendedAuth0.users, "has_existed") as user_has_existed:
        user_has_existed.return_value = True
        yield user_has_existed


def test_clear_up_user(
    ExtendedAuth0,
    fixture_user_has_existed,
    fixture_users_get_user_groups,
    fixture_group_delete_member,
    fixture_user_delete,
):
    user_id = "remove_user_id"
    ExtendedAuth0.clear_up_user(user_id)
    domain = settings.AUTH0["authorization_extension_url"]
    fixture_group_delete_member.assert_has_calls(
        [
            call(
                f"{domain}/groups/2a1e2b9f-3435-4954-8c5d-56e8e9ce763f/members",
                data=["remove_user_id"],
            ),
            call(
                f"{domain}/groups/81097bea-f7a3-48b6-a3fc-e2c3eb6c1ace/members",
                data=["remove_user_id"],
            ),
        ]
    )
    domain = settings.AUTH0["domain"]
    fixture_user_delete.assert_called_with(f"https://{domain}/api/v2/users/{user_id}")


@pytest.fixture
def fixture_group_members_200(ExtendedAuth0):
    with patch.object(ExtendedAuth0.groups, "all") as request:
        request.side_effect = [
            {
                "total": 200,
                "users": [
                    {
                        "name": f"Test Group Member {(i * 100) + j}",
                        "email": f"test{(i * 100) + j}@example.com",
                        "user_id": f"github|{(i * 100) + j}",
                    }
                    for j in range(100)
                ],
            }
            for i in range(2)
        ]
        yield


def test_group_member_more_than_100(ExtendedAuth0, fixture_group_members_200):
    members = ExtendedAuth0.groups.get_group_members(group_id="foo-id-1")
    assert len(members) == 200


@pytest.fixture
def fixture_client_search_first_match(ExtendedAuth0):
    with patch.object(
        ExtendedAuth0.clients, "search_first_match"
    ) as client_search_first_match:
        client_search_first_match.return_value = {"client_id": "new_client_id"}
        yield client_search_first_match


def test_update_client_auth_connections(
    ExtendedAuth0,
    fixture_connection_disable_client,
    fixture_connection_enable_client,
    fixture_connection_get_all,
    fixture_client_search_first_match,
):
    new_client_id = "new_client_id"

    connection1 = {
        "name": "connection 1",
        "id": "con_0000000000000002",
        "enabled_clients": ["new_client_id"],
    }
    connection2 = {
        "name": "connection 2",
        "id": "con_0000000000000003",
        "enabled_clients": ["new_client_id"],
    }

    ExtendedAuth0.update_client_auth_connections(
        app_name="test",
        client_id=new_client_id,
        new_conns={"email": {}, "connection 1": {}},
        existing_conns=["email", "connection 2"],
    )

    fixture_connection_disable_client.assert_has_calls(
        [call(connection2, new_client_id)],
    )
    fixture_connection_enable_client.assert_has_calls(
        [call(connection1, new_client_id)],
    )


@pytest.fixture
def fixture_connection_create(ExtendedAuth0):
    with patch.object(ExtendedAuth0.connections, "create") as connection_create:
        connection_create.return_value = {
            "name": "test_nomis_connection",
            "id": "new_connection",
            "client_id": "test_nomis_connection_id",
        }
        yield connection_create


def test_create_custom_connection(ExtendedAuth0, fixture_connection_create):
    def _clean_string(content):
        return content.replace(" ", "").replace("\n", "")

    ExtendedAuth0.connections.create_custom_connection(
        "auth0_nomis",
        input_values={
            "name": "test_nomis_connection",
            "client_id": "test_nomis_connection_id",
            "client_secret": "WNXFkM3FCTXJhUWs0Q1NwcKFu",
        },
    )
    fixture_connection_create.assert_called_once_with(ANY)
    with open("./tests/api/fixtures/nomis_body.json") as body_file:
        expected = json.loads(body_file.read())

    # Check whether the json argument passed into connection.create is expected
    call = fixture_connection_create.call_args
    call_args, call_kwargs = call
    actual_arg = call_args[0]

    actual_arg["options"]["scripts"]["fetchUserProfile"] = _clean_string(
        actual_arg["options"]["scripts"]["fetchUserProfile"]
    )
    expected["options"]["scripts"]["fetchUserProfile"] = _clean_string(
        expected["options"]["scripts"]["fetchUserProfile"]
    )
    assert actual_arg == expected


def test_create_custom_connection_with_allowed_error(ExtendedAuth0):
    with patch.object(ExtendedAuth0.connections, "create") as connection_create:
        connection_create.side_effect = exceptions.Auth0Error(
            409, 409, "The connection name existed already"
        )
        ExtendedAuth0.connections.create_custom_connection(
            "auth0_nomis",
            input_values={
                "name": "test_nomis_connection",
                "client_id": "test_nomis_connection_id",
                "client_secret": "WNXFkM3FCTXJhUWs0Q1NwcKFu",
            },
        )
        connection_create.assert_called_once_with(ANY)


def test_create_custom_connection_with_notallowed_error(ExtendedAuth0):
    with patch.object(ExtendedAuth0.connections, "create") as connection_create:
        connection_create.side_effect = exceptions.Auth0Error(400, 400, "Error")
        with pytest.raises(auth0.Auth0Error, match="400: Error"):
            ExtendedAuth0.connections.create_custom_connection(
                "auth0_nomis",
                input_values={
                    "name": "test_nomis_connection",
                    "client_id": "test_nomis_connection_id",
                    "client_secret": "WNXFkM3FCTXJhUWs0Q1NwcKFu",
                },
            )
        connection_create.assert_called_once_with(ANY)
