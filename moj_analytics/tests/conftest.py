import json
from unittest import mock

import pytest
from responses import RequestsMock

from moj_analytics.auth0_client import (
    Auth0,
    AuthorizationAPI,
    Client,
    Connection,
    Group,
    ManagementAPI,
    Permission,
    Role
)


@pytest.fixture
def config():
    return {
        'client_id': 'auth0_client_id',
        'client_secret': 'auth0_client_secret',
        'domain': 'example.com',
        'authz_url': 'https://example.com',
        'authz_audience': 'urn:auth0-authz-api',
    }


@pytest.yield_fixture
def responses():
    with RequestsMock(assert_all_requests_are_fired=False) as patch:
        yield patch


def clear_previous(responses, method, url):
    match = None

    for match in responses._matches:

        if match.method == method and match.url == url:
            break

    else:
        match = None

    if match:
        responses._matches.remove(match)


def json_response(data, status=200, headers={}):
    headers.setdefault('Content-Type', 'application/json')

    def handle(request):

        assert request.headers['Authorization'] == 'Bearer {token}'.format(
            token='test-access-token')

        payload = data
        if callable(data):
            request.json = json.loads(request.body.decode('utf-8'))
            payload = data(request)

        return (status, headers, json.dumps(payload))

    return handle


@pytest.fixture
def state():
    return {}


@pytest.fixture
def auth0(config):
    return Auth0(config['client_id'], config['client_secret'], config['domain'])


@pytest.yield_fixture
def given_valid_api_client_credentials():

    with mock.patch('moj_analytics.auth0_client.authentication.GetToken') as gt:
        gt.return_value.client_credentials.return_value = {
            'access_token': 'test-access-token'
        }
        yield


@pytest.fixture
def given_access_to_the_management_api(auth0, config, responses):
    auth0.access(ManagementAPI(config['domain']))

    endpoint = 'https://{domain}/api/v2/clients'.format(**config)

    responses.add_callback('POST', endpoint, json_response(
        lambda request: Client(
            name=request.json['name'],
            client_id='new-client-id',
            client_secret='new-client-secret'
        )
    ))

    responses.add_callback('GET', endpoint, json_response(lambda request: [
        Client(name='client1')
    ]))


@pytest.fixture
def mock_resources(responses):

    def do_mock(base_url, resource_name, data, json_format=None):

        endpoint = '{base_url}/{resource_name}'.format(
            base_url=base_url,
            resource_name=resource_name)

        clear_previous(responses, 'GET', endpoint)

        for counter, resource in enumerate(data):
            resource['_id'] = counter

        if json_format is None:
            json_format = identity

        responses.add_callback('GET', endpoint, json_response(
            json_format(resource_name, data)))

        if resource_name == 'roles':

            for role in data:
                responses.add_callback(
                    'PUT',
                    '{}/{}'.format(endpoint, resource['_id']),
                    json_response({}))

        if resource_name == 'groups':

            for group in data:
                responses.add_callback(
                    'PATCH',
                    '{}/{}/roles'.format(endpoint, group['_id']),
                    json_response({}))

    return do_mock


def identity(data):
    return data


def authz_format(resource_name, data):
    return {
        resource_name: data,
        'total': len(data)
    }


@pytest.fixture(params=[
    [],
    [Client(name='client1')],
    [Client(name='client{}'.format(i)) for i in range(10)]
])
def given_a_number_of_clients_exist(request, config, mock_resources, state):
    mock_resources(config['management_url'], 'clients', request.param)
    state['clients'] = request.params


@pytest.fixture(params=[
    [],
    [Connection(name='connection1')],
    [Connection(name='connection{}'.format(i)) for i in range(10)]
])
def given_a_number_of_connections_exist(request, config, responses, state):
    mock_resources(config['management_url'], 'connections', request.param)
    state['connections'] = request.param


@pytest.fixture
def given_access_to_the_authorization_api(auth0, config, responses):
    auth0.access(AuthorizationAPI(
        config['authz_url'], config['authz_audience']))

    endpoint = '{authz_url}/permissions'.format(**config)
    responses.add_callback('POST', endpoint, json_response(lambda request: {
        'name': request.json['name'],
        'description': request.json['description'],
    }))
    responses.add_callback('GET', endpoint, json_response({
        'permissions': [],
        'total': 0
    }))

    endpoint = '{authz_url}/roles'.format(**config)
    responses.add_callback('GET', endpoint, json_response({
        'roles': [],
        'total': 0
    }))
    responses.add_callback('POST', endpoint, json_response(lambda request: {
        'name': request.json['name'],
        'description': request.json['description']
    }))

    endpoint = '{authz_url}/groups'.format(**config)
    responses.add_callback('GET', endpoint, json_response({
        'roles': [],
        'total': 0
    }))


@pytest.fixture
def given_a_group_exists(request, config, mock_resources, state):
    data = [Group(name='group1')]
    mock_resources(config['authz_url'], 'groups', data, authz_format)
    state['groups'] = data


@pytest.fixture
def given_a_permission_exists(request, config, mock_resources, state):
    data = [Permission(name='perm1', applicationId='app1')]
    mock_resources(config['authz_url'], 'permissions', data, authz_format)
    state['permissions'] = data


@pytest.fixture
def given_a_role_exists(request, config, mock_resources, state):
    data = [Role(name='role1', applicationId='app1')]
    mock_resources(config['authz_url'], 'roles', data, authz_format)
    state['roles'] = data
