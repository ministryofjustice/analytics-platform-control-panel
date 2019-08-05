import json

from model_mommy import mommy
import pytest
from rest_framework import status
from rest_framework.reverse import reverse

from controlpanel.api.models import UserS3Bucket
import controlpanel.api.rules


@pytest.fixture
def users(users):
    users.update({
        "bucket_admin": mommy.make(
            "api.User",
            username="bucket_admin",
            auth0_id="github|user_4",
        ),
    })
    return users


@pytest.fixture
def bucket():
    return mommy.make("api.S3Bucket")


@pytest.fixture
def users3bucket(bucket, users):
    mommy.make(
        "api.UserS3Bucket",
        user=users['bucket_admin'],
        s3bucket=bucket,
        access_level=UserS3Bucket.READONLY,
        is_admin=True,
    )
    return mommy.make(
        "api.UserS3Bucket",
        user=users['normal_user'],
        s3bucket=bucket,
        access_level=UserS3Bucket.READONLY,
    )


def list(client, *args):
    return client.get(reverse('users3bucket-list'))


def create(client, _, bucket, users, *args):
    data = {
        'user': users['other_user'].auth0_id,
        's3bucket': bucket.id,
        'access_level': UserS3Bucket.READWRITE,
        'is_admin': True,
    }
    return client.post(
        reverse('users3bucket-list'),
        json.dumps(data),
        content_type="application/json",
    )


def retrieve(client, users3bucket, *args):
    return client.get(reverse('users3bucket-detail', (users3bucket.id,)))


def update(client, users3bucket, bucket, users, *args):
    data = {
        'user': users['normal_user'].auth0_id,
        's3bucket': bucket.id,
        "access_level": UserS3Bucket.READWRITE,
        'is_admin': False,
    }
    return client.put(
        reverse('users3bucket-detail', (users3bucket.id,)),
        json.dumps(data),
        content_type="application/json",
    )


def delete(client, users3bucket, *args):
    return client.delete(reverse('users3bucket-detail', (users3bucket.id,)))


@pytest.mark.parametrize(
    'view,user,expected_status',
    [
        (list, 'superuser', status.HTTP_200_OK),
        (create, 'superuser', status.HTTP_201_CREATED),
        (retrieve, 'superuser', status.HTTP_200_OK),
        (update, 'superuser', status.HTTP_200_OK),
        (delete, 'superuser', status.HTTP_204_NO_CONTENT),

        (list, 'normal_user', status.HTTP_200_OK),
        (create, 'normal_user', status.HTTP_403_FORBIDDEN),
        (retrieve, 'normal_user', status.HTTP_403_FORBIDDEN),
        (update, 'normal_user', status.HTTP_403_FORBIDDEN),
        (delete, 'normal_user', status.HTTP_403_FORBIDDEN),

        (list, 'bucket_admin', status.HTTP_200_OK),
        (create, 'bucket_admin', status.HTTP_201_CREATED),
        (retrieve, 'bucket_admin', status.HTTP_200_OK),
        (update, 'bucket_admin', status.HTTP_200_OK),
        (delete, 'bucket_admin', status.HTTP_204_NO_CONTENT),
    ],
)
@pytest.mark.django_db
def test_permission(
        client, users3bucket, bucket, users, view, user, expected_status):
    client.force_login(users[user])
    response = view(client, users3bucket, bucket, users)
    assert response.status_code == expected_status

