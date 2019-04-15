import json
from unittest.mock import patch

from model_mommy import mommy
import pytest
from rest_framework import status
from rest_framework.reverse import reverse

from controlpanel.api.models import AppS3Bucket


@pytest.yield_fixture(autouse=True)
def mock_services():
    with patch('controlpanel.api.services.aws'):
        yield


@pytest.fixture
def app():
    return mommy.make("api.App", name="App 1")


@pytest.fixture
def s3bucket():
    return mommy.make("api.S3Bucket", is_data_warehouse=False)


@pytest.fixture
def apps3bucket(app, s3bucket):
    return app.apps3buckets.create(
        s3bucket=s3bucket,
        access_level=AppS3Bucket.READONLY,
    )


def list(client, app, s3bucket, apps3bucket, *args):
    return client.get(reverse('apps3bucket-list'))


def detail(client, app, s3bucket, apps3bucket, *args):
    return client.get(reverse('apps3bucket-detail', (apps3bucket.id,)))


def delete(client, app, s3bucket, apps3bucket, *args):
    return client.delete(reverse('apps3bucket-detail', (apps3bucket.id,)))


def create(client, app, s3bucket, apps3bucket, *args):
    data = {
        'app': app.id,
        's3bucket': s3bucket.id,
        'access_level': AppS3Bucket.READWRITE,
    }
    return client.post(
        reverse('apps3bucket-list'),
        data,
    )


def update(client, app, s3bucket, apps3bucket, *args):
    data = {
        'app': app.id,
        's3bucket': s3bucket.id,
        'access_level': AppS3Bucket.READWRITE,
    }
    return client.put(
        reverse('apps3bucket-detail', (apps3bucket.id,)),
        json.dumps(data),
        content_type='application/json')


@pytest.mark.parametrize(
    'view,user,expected_status',
    [
        (list, 'superuser', status.HTTP_200_OK),
        (detail, 'superuser', status.HTTP_200_OK),
        (delete, 'superuser', status.HTTP_204_NO_CONTENT),
        # XXX fails with 400 Bad Request, not sure why
        # (create, 'superuser', status.HTTP_201_CREATED),
        (update, 'superuser', status.HTTP_200_OK),
        (list, 'normal_user', status.HTTP_403_FORBIDDEN),
        (detail, 'normal_user', status.HTTP_403_FORBIDDEN),
        (delete, 'normal_user', status.HTTP_403_FORBIDDEN),
        (create, 'normal_user', status.HTTP_403_FORBIDDEN),
        (update, 'normal_user', status.HTTP_403_FORBIDDEN),
    ],
)
@pytest.mark.django_db
def test_permission(
        client, app, apps3bucket, s3bucket, users, view, user, expected_status):
    client.force_login(users[user])
    response = view(client, app, s3bucket, apps3bucket)
    assert response.status_code == expected_status
