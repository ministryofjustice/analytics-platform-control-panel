import pytest

from moj_analytics.auth0_client import (
    Client,
    Group,
    Permission,
    Role
)


class TestAuth0Client(object):

    @pytest.mark.usefixtures(
        'given_valid_api_client_credentials',
        'given_access_to_the_management_api',
    )
    def test_it_can_create_a_client(self, auth0):

        client = auth0.management.get_or_create(Client(name='test-client'))

        assert client['client_id'] == 'new-client-id'
        assert client['client_secret'] == 'new-client-secret'

    @pytest.mark.usefixtures(
        'given_valid_api_client_credentials',
        'given_access_to_the_authorization_api',
        'given_a_permission_exists'
    )
    def test_it_can_get_a_permission(self, auth0, responses, state):

        permission = auth0.authorization.get(Permission(
            name='perm1',
            applicationId='app1'
        ))

        if len(state['permissions']) == 0:
            assert permission is None

        else:
            assert permission

    @pytest.mark.usefixtures(
        'given_valid_api_client_credentials',
        'given_access_to_the_authorization_api'
    )
    def test_it_can_create_a_permission(self, auth0):

        permission = auth0.authorization.get_or_create(Permission(
            name='view:app',
            applicationId='new-client-id'
        ))

        assert permission['description'] == 'view:app'

    @pytest.mark.usefixtures(
        'given_valid_api_client_credentials',
        'given_access_to_the_authorization_api',
    )
    def test_it_can_create_a_role(self, auth0):

        role = auth0.authorization.create(
            Role(name='role1', applicationId='new-client-id'))

        assert role['description'] == 'role1'

    @pytest.mark.usefixtures(
        'given_valid_api_client_credentials',
        'given_access_to_the_authorization_api',
        'given_a_role_exists',
        'given_a_permission_exists'
    )
    def test_it_can_add_a_permission_to_a_role(self, auth0):

        role = auth0.authorization.get(Role(name='role1', applicationId='app1'))
        permission = auth0.authorization.get(
            Permission(name='perm1', applicationId='app1'))

        role.add_permission(permission)

        assert permission['_id'] in role['permissions']

    @pytest.mark.usefixtures(
        'given_valid_api_client_credentials',
        'given_access_to_the_authorization_api',
        'given_a_group_exists',
        'given_a_role_exists'
    )
    def test_it_can_add_a_role_to_a_group(self, auth0, responses):

        group = auth0.authorization.get(Group(name='group1'))
        role = auth0.authorization.get(Role(name='role1', applicationId='app1'))

        group.add_role(role)

        calls = [
            call
            for call in responses.calls
            if call.request.method == 'PATCH'
            and call.request.url.endswith('groups/{_id}/roles'.format(**group))]
        assert len(calls) == 1
