import json

from model_mommy import mommy
import pytest
from rest_framework import status
from rest_framework.reverse import reverse

from controlpanel.api.models import AppS3Bucket
import controlpanel.api.rules


@pytest.fixture
def users(users):
    users.update({
        "app_admin": mommy.make(
            "api.User",
            username="dave",
            auth0_id="github|user_4",
        ),
        "bucket_admin": mommy.make(
            "api.User",
            username="ethel",
            auth0_id='github|user_5',
        ),
        "app_bucket_admin": mommy.make(
            "api.User",
            username="fred",
            auth0_id='github|user_6',
        ),
    })
    return users

@pytest.fixture
def app(users):
    app = mommy.make("api.App", name="App 1")
    mommy.make(
        "api.UserApp",
        app=app,
        user=users['app_admin'],
        is_admin=True,
    )
    mommy.make(
        "api.UserApp",
        app=app,
        user=users['app_bucket_admin'],
        is_admin=True,
    )
    return app


@pytest.fixture
def buckets(users):
    buckets = {
        'first': mommy.make("api.S3Bucket", is_data_warehouse=False),
        'other': mommy.make('api.S3Bucket', is_data_warehouse=False),
    }
    mommy.make(
        'api.UserS3Bucket',
        user=users['bucket_admin'],
        s3bucket=buckets['first'],
        is_admin=True,
    )
    mommy.make(
        'api.UserS3Bucket',
        user=users['app_bucket_admin'],
        s3bucket=buckets['first'],
        is_admin=True,
    )
    return buckets


@pytest.fixture
def apps3bucket(app, buckets):
    return app.apps3buckets.create(
        s3bucket=buckets['first'],
        access_level=AppS3Bucket.READONLY,
    )


def list(client, *args):
    return client.get(reverse('apps3bucket-list'))


def detail(client, apps3bucket, *args):
    return client.get(reverse('apps3bucket-detail', (apps3bucket.id,)))


def delete(client, apps3bucket, *args):
    return client.delete(reverse('apps3bucket-detail', (apps3bucket.id,)))


def create(client, apps3bucket, app, buckets, *args):
    data = {
        'app': app.id,
        's3bucket': buckets['other'].id,
        'access_level': AppS3Bucket.READWRITE,
    }
    return client.post(
        reverse('apps3bucket-list'),
        data,
    )


def update(client, apps3bucket, app, buckets, *args):
    data = {
        'app': app.id,
        's3bucket': buckets['first'].id,
        'access_level': AppS3Bucket.READWRITE,
    }
    return client.put(
        reverse('apps3bucket-detail', (apps3bucket.id,)),
        json.dumps(data),
        content_type='application/json',
    )


@pytest.mark.parametrize(
    'view,user,expected_status',
    [
        (list, 'superuser', status.HTTP_200_OK),
        (detail, 'superuser', status.HTTP_200_OK),
        (delete, 'superuser', status.HTTP_204_NO_CONTENT),
        (create, 'superuser', status.HTTP_201_CREATED),
        (update, 'superuser', status.HTTP_200_OK),

        (list, 'normal_user', status.HTTP_200_OK),
        (detail, 'normal_user', status.HTTP_404_NOT_FOUND),
        (delete, 'normal_user', status.HTTP_403_FORBIDDEN),
        (create, 'normal_user', status.HTTP_403_FORBIDDEN),
        (update, 'normal_user', status.HTTP_404_NOT_FOUND),

        (list, 'app_admin', status.HTTP_200_OK),
        (detail, 'app_admin', status.HTTP_200_OK),
        (delete, 'app_admin', status.HTTP_403_FORBIDDEN),
        (create, 'app_admin', status.HTTP_403_FORBIDDEN),
        (update, 'app_admin', status.HTTP_403_FORBIDDEN),

        (list, 'bucket_admin', status.HTTP_200_OK),
        (detail, 'bucket_admin', status.HTTP_200_OK),
        (delete, 'bucket_admin', status.HTTP_403_FORBIDDEN),
        (create, 'bucket_admin', status.HTTP_403_FORBIDDEN),
        (update, 'bucket_admin', status.HTTP_403_FORBIDDEN),

        (list, 'app_bucket_admin', status.HTTP_200_OK),
        (detail, 'app_bucket_admin', status.HTTP_200_OK),
        (delete, 'app_bucket_admin', status.HTTP_403_FORBIDDEN),
        (create, 'app_bucket_admin', status.HTTP_403_FORBIDDEN),
        (update, 'app_bucket_admin', status.HTTP_200_OK),
    ],
)
@pytest.mark.django_db
def test_permission(
        client, app, apps3bucket, buckets, users, view, user, expected_status):
    client.force_login(users[user])
    response = view(client, apps3bucket, app, buckets)
    assert response.status_code == expected_status
