from botocore.exceptions import ClientError
from model_mommy import mommy

from rest_framework import status
from rest_framework.reverse import reverse
from unittest.mock import patch

from controlpanel.api.models import App
from tests.api.fixtures.aws import *


@pytest.fixture
def app():
    return mommy.make(
        'api.App',
        repo_url='https://example.com/foo.git',
    )


@pytest.fixture(autouse=True)
def models(app, users):
    with patch('controlpanel.api.aws.AWSBucket.create_bucket') as create_bucket:
        mommy.make('api.App')
        mommy.make('api.AppS3Bucket', app=app)
        mommy.make('api.UserApp', app=app, user=users['superuser'])


def test_list(client):
    response = client.get(reverse('app-list'))
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data['results']) == 2


def test_list_filter_by_repo_url(client, app):
    response = client.get(
        reverse('app-list'),
        {'repo_url': app.repo_url},
    )

    assert response.status_code == status.HTTP_200_OK
    results = response.data['results']
    assert len(results) == 1
    assert results[0]['id'] == app.id


def test_detail(client, app):
    response = client.get(reverse('app-detail', (app.id,)))
    assert response.status_code == status.HTTP_200_OK

    expected_fields = {
        'id',
        'url',
        'name',
        'description',
        'slug',
        'repo_url',
        'iam_role_name',
        'created_by',
        'apps3buckets',
        'userapps',
    }
    assert expected_fields == set(response.data)
    assert response.data['iam_role_name'] == app.iam_role_name

    apps3bucket = response.data['apps3buckets'][0]
    expected_fields = {'id', 'url', 's3bucket', 'access_level'}
    assert set(apps3bucket) == expected_fields

    expected_fields = {
        'id',
        'url',
        'name',
        'arn',
        'created_by',
        'is_data_warehouse',
    }
    assert set(apps3bucket['s3bucket']) == expected_fields

    userapp = response.data['userapps'][0]
    expected_fields = {'id', 'user', 'is_admin'}
    assert set(userapp) == expected_fields

    expected_fields = {
        'auth0_id',
        'url',
        'username',
        'name',
        'email',
    }
    assert set(userapp['user']) == expected_fields


@pytest.yield_fixture
def authz():
    with patch("controlpanel.api.auth0.ExtendedAuth0") as authz:
        yield authz()


def test_delete(client, app, authz, secretsmanager):
    with patch('controlpanel.api.aws.AWSRole.delete_role') as delete_role:
        response = client.delete(reverse('app-detail', (app.id,)))
        assert response.status_code == status.HTTP_204_NO_CONTENT

        authz.clear_up_app.assert_called_with(app_name=app.slug, group_name=app.slug)
        delete_role.assert_called_with(app.iam_role_name)

        response = client.get(reverse('app-detail', (app.id,)))
        assert response.status_code == status.HTTP_404_NOT_FOUND


def test_create(client, users):
    with patch('controlpanel.api.aws.AWSRole.create_role') as create_app_role:
        data = {'name': 'bar', 'repo_url': 'https://example.com/bar.git'}
        response = client.post(reverse('app-list'), data)
        assert response.status_code == status.HTTP_201_CREATED

        create_app_role.assert_called()

        assert response.data['created_by'] == users['superuser'].auth0_id
        assert response.data['repo_url'] == 'https://example.com/bar'


def test_update(client, app):
    data = {'name': 'foo', 'repo_url': 'http://foo.com.git'}
    response = client.put(
        reverse('app-detail', (app.id,)),
        data,
        content_type="application/json",
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.data['name'] == data['name']
    assert response.data['repo_url'] == 'http://foo.com'


def test_aws_error_and_transaction(client):
    with patch('controlpanel.api.aws.AWSRole.create_role') as create_app_role:
        create_app_role.side_effect = ClientError({}, "CreateRole")
        data = {'name': 'quux', 'repo_url': 'https://example.com/quux.git'}

        with pytest.raises(ClientError):
            client.post(reverse('app-list'), data)

        with pytest.raises(App.DoesNotExist):
            App.objects.get(name=data['name'])
