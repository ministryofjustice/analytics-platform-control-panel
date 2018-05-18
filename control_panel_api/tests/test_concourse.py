from unittest import mock

from django.conf import settings
import pytest

from control_panel_api.concourse import Concourse


PIPELINES_JSON = [
    {
        'id': 1,
        'name': 'test',
        'team_name': 'main',
        'public': False,
        'paused': True
    },
    {
        'id': 2,
        'name': 'test-2',
        'team_name': 'main',
        'public': False,
        'paused': True
    }
]

PIPELINE_CONFIG_JSON = {
    'config': {
        'groups': None,
        'resources': None,
        'resource_types': None,
        'jobs': None
    },
    'errors': None,
    'raw_config':
    '{"groups":null,"resources":null,"resource_types":null,"jobs":null}'
}


def test_concourse_login():
    url = settings.CONCOURSE["url"]
    team = settings.CONCOURSE['team']
    username = settings.CONCOURSE['username']
    password = settings.CONCOURSE['password']

    concourse = Concourse(url, team, username, password)

    with mock.patch('control_panel_api.concourse.requests.get') as get:
        get.return_value.json.return_value = {
            'type': 'Bearer',
            'value': 'DUMMYTOKEN'}

        concourse.login()

        get.assert_called_with(
            f'{url}/auth/basic/token?team_name={team}',
            auth=(username, password))


@pytest.fixture
def logged_in_client():
    concourse = Concourse(**settings.CONCOURSE)
    concourse.session.headers['Authorization'] = 'Bearer DUMMYTOKEN'
    return concourse


@pytest.yield_fixture
def atc_request():
    request = 'control_panel_api.concourse.requests.Session.request'
    with mock.patch(request) as req:
        yield req


def test_concourse_get_pipelines(logged_in_client, atc_request):
    atc_request.return_value.json.return_value = PIPELINES_JSON

    pipelines = logged_in_client.pipelines

    atc_request.assert_called_with(
        'GET',
        f'{settings.CONCOURSE["url"]}/api/v1/teams/main/pipelines',
        headers={},
        data=None,
        params={})


def test_concourse_set_pipeline(logged_in_client, atc_request):
    api_url = f'{settings.CONCOURSE["url"]}/api/v1/teams/main'

    def req(method, url, headers={}, data=None, params={}):
        response = mock.MagicMock()

        if url == f'{api_url}/pipelines':
            response.json.return_value = PIPELINES_JSON

        if url == f'{api_url}/pipelines/test/config':
            if method == 'GET':
                response.json.return_value = PIPELINE_CONFIG_JSON
                response.headers = {
                    'X-Concourse-Config-Version': None
                }

        return response

    atc_request.side_effect = req

    yaml = 'test: foo'

    logged_in_client.pipelines['test'] = yaml

    atc_request.assert_any_call(
        'GET',
        f'{api_url}/pipelines/test/config',
        headers={},
        data=None,
        params={})

    atc_request.assert_any_call(
        'PUT',
        f'{api_url}/pipelines/test/config',
        headers={
            'x-concourse-config-version': None,
            'content-type': 'application/x-yaml'
        },
        data=str(yaml),
        params={})
