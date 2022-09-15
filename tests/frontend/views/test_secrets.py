from unittest.mock import patch

from django.contrib.messages import get_messages
from django.urls import reverse
from controlpanel.settings.common import SECRET_KEY
from model_mommy import mommy
from rest_framework import status

from controlpanel.api import auth0
from tests.api.fixtures.aws import *


NUM_APPS = 3


@pytest.fixture(autouse=True)
def enable_db_for_all_tests(db):
    pass


@pytest.yield_fixture(autouse=True)
def github_api_token():
    with patch('controlpanel.api.models.user.auth0.ExtendedAuth0') as ExtendedAuth0:
        ExtendedAuth0.return_value.users.get.return_value = {
            'identities': [
                {
                    'provider': 'github',
                    'access_token': 'dummy-access-token',
                },
            ],
        }
        yield ExtendedAuth0.return_value


@pytest.fixture(autouse=True)
def users(users):
    users.update({
        'app_admin': mommy.make('api.User', username='app_admin'),
    })
    return users


@pytest.fixture(autouse=True)
def app(users):
    mommy.make('api.App', NUM_APPS - 1)
    app = mommy.make('api.App')
    mommy.make('api.UserApp', user=users['app_admin'], app=app, is_admin=True)
    return app


@pytest.yield_fixture(autouse=True)
def repos(github):
    test_repo = {
        'full_name': 'Test App',
        'html_url': 'https://github.com/moj-analytical-services/test_app',
    }
    org = github.get_organization.return_value
    org.get_repos.return_value = [test_repo]
    github.get_repo.return_value = test_repo
    yield github


@pytest.fixture(autouse=True)
def s3buckets(app):
    with patch('controlpanel.api.aws.AWSBucket.create_bucket') as create_bucket:
        buckets = {
            'not_connected': mommy.make('api.S3Bucket'),
            'connected': mommy.make('api.S3Bucket'),
        }
        return buckets


@pytest.fixture
def apps3bucket(app, s3buckets):
    return mommy.make('api.AppS3Bucket', app=app, s3bucket=s3buckets['connected'])


@pytest.yield_fixture
def fixture_get_secret():
    with patch("controlpanel.api.aws.AWSSecretManager.get_secret_if_found") as get_secret_if_found:
        get_secret_if_found.return_value = {
            "client_id": "testing_client_id1",
            "client_secret": "testing",
        }
        yield get_secret_if_found

@pytest.yield_fixture
def fixture_create_update_secret():
    with patch("controlpanel.api.aws.AWSSecretManager.create_or_update") as create_or_update:
        yield create_or_update

@pytest.yield_fixture
def fixture_get_secret_value():
    with patch('controlpanel.api.aws.AWSSecretManager.get_secret') as get_secret_value:
        get_secret_value.return_value = dict(disable_authentication = True)
        yield get_secret_value

@pytest.yield_fixture
def fixture_update_secret():
    with patch('controlpanel.api.aws.AWSSecretManager.update_secret') as update_secret:
        yield update_secret

def detail(client, app, *args):
    return client.get(reverse('manage-app', kwargs={'pk': app.id}))

def add_update_secret(client, app, key=None, *args):
    return client.get(reverse('add-secret', kwargs=dict(pk=app.id, secret_key=key)))

def add_secret(client, app, key=None, *args):
    return client.get(reverse('add-secret', kwargs={'pk': app.id, 'secret_key': key}))

def add_secret_post(client, app, key=None, data={}, *args):
    return client.post(reverse('add-secret', kwargs={'pk': app.id, 'secret_key': key}), data)

def delete_secret_post(client, app, key=None, *args):
    return client.post(reverse('delete-secret', kwargs={'pk': app.id, 'secret_key': key}))

@pytest.mark.parametrize(
    'view,user,expected_status', [
        (detail, 'superuser', status.HTTP_200_OK),
    ],
)
def test_permissions(client, app, s3buckets, users, view, user, expected_status, fixture_get_secret):
    client.force_login(users[user])
    response = view(client, app, users, s3buckets)
    delete_form = '<form action="/webapps/3/secrets/delete/disable_authentication/" method="post"'

    element = f'<a href="/webapps/{NUM_APPS}/secrets/add/disable_authentication/"  class="govuk-button" >disable_authentication</a>'
    body = str(response.content)
    assert element in body
    assert delete_form not in body

    fixture_get_secret.return_value = {'disable_authentication': True, **fixture_get_secret.return_value}
    response = view(client, app, users, s3buckets)
    body = str(response.content)
    assert delete_form in body

    fixture_get_secret.return_value = {**fixture_get_secret.return_value, 'disable_authentication': False}
    response = view(client, app, users, s3buckets)
    body = str(response.content)
    assert delete_form in body

@pytest.mark.parametrize(
    'user,secret_key,expected_status',[
        ['superuser', 'disable_authentication', 200],
        ['superuser', 'unknown_key', 404]
    ]
)
def test_add_secret(client, app, users, user, secret_key, expected_status, fixture_get_secret_value):
    client.force_login(users[user])
    response = add_update_secret(client, app, key=secret_key)
    assert response.status_code == expected_status

@pytest.mark.parametrize(
    'user,secret_key,expected_status,set_secrets',[
        ['superuser', 'disable_authentication', 302, {'disable_authentication': True}]
    ]
)
def test_view_add_update_secret_page(client, app, users, user, secret_key, expected_status, set_secrets, fixture_get_secret_value, fixture_create_update_secret):
    client.force_login(users[user])
    response = add_secret(client, app, key=secret_key)
    input = '<label class="govuk-label govuk-checkboxes__label " for="secret_value-1">'
    assert input in str(response.content)

    response = add_secret_post(client, app, key=secret_key, data = dict(secret_value=1))
    assert response.status_code == expected_status
    assert response.get('Location') == reverse('manage-app', kwargs={'pk': app.id})
    fixture_create_update_secret.assert_called_with(app.app_aws_secret_name, set_secrets)        

@pytest.mark.parametrize(
    'user,secret_key,expected_status,set_secrets',[
        ['superuser', 'disable_authentication', 302, {'disable_authentication': True}]
    ]
)
def test_secret_delete(client, app, users, user, secret_key, expected_status, set_secrets, fixture_get_secret, fixture_update_secret):
    client.force_login(users[user])
    response = client.get(reverse('delete-secret', kwargs={'pk': app.id, 'secret_key': secret_key}))
    assert response.status_code == 405

    fixture_get_secret.return_value = {}
    response = delete_secret_post(client, app, key=secret_key)
    assert response.status_code == 302

    messages = get_messages(response.wsgi_request)
    error = 'failed to find disable_authentication in secrets'
    assert error in [m.message for m in messages]

    fixture_get_secret.return_value = set_secrets

    response = delete_secret_post(client, app, key=secret_key)
    fixture_update_secret.assert_called_with(app.app_aws_secret_name, {}, delete_keys=[secret_key])
    response.status_code == 302