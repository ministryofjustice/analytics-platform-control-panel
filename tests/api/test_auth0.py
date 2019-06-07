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
