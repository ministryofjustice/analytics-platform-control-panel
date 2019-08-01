from django.urls import reverse
from model_mommy import mommy
import pytest
from rest_framework import status

from controlpanel.api.models import UserS3Bucket


@pytest.fixture(autouse=True)
def enable_db_for_all_tests(db):
    pass


@pytest.fixture
def users(users):
    users.update({
        'bucket_viewer': mommy.make('api.User', username='bucket_viewer'),
        'bucket_admin': mommy.make('api.User', username='bucket_admin'),
    })
    return users


@pytest.fixture
def bucket():
    return mommy.make('api.S3Bucket', is_data_warehouse=True)


@pytest.fixture(autouse=True)
def users3bucket(bucket, users):
    mommy.make(
        'api.UserS3Bucket',
        s3bucket=bucket,
        user=users['bucket_viewer'],
        access_level=UserS3Bucket.READONLY,
    )
    return mommy.make(
        'api.UserS3Bucket',
        s3bucket=bucket,
        user=users['bucket_admin'],
        access_level=UserS3Bucket.READWRITE,
        is_admin=True,
    )


def list_warehouse(client, *args):
    return client.get(reverse('list-warehouse-datasources'))


def list_app_data(client, *args):
    return client.get(reverse('list-webapp-datasources'))


def list_all(client, *args):
    return client.get(reverse('list-all-datasources'))


def detail(client, bucket, *args):
    return client.get(reverse('manage-datasource', kwargs={'pk': bucket.id}))


def create(client, *args):
    data = {
        'name': 'new_bucket',
    }
    return client.post(reverse('create-datasource') + '?type=warehouse', data)


def delete(client, bucket, *args):
    return client.delete(reverse('delete-datasource', kwargs={'pk': bucket.id}))


@pytest.mark.parametrize(
    'view,user,expected_status',
    [
        (list_warehouse, 'superuser', status.HTTP_200_OK),
        (list_warehouse, 'bucket_admin', status.HTTP_200_OK),
        (list_warehouse, 'normal_user', status.HTTP_200_OK),

        (list_app_data, 'superuser', status.HTTP_200_OK),
        (list_app_data, 'bucket_admin', status.HTTP_200_OK),
        (list_app_data, 'normal_user', status.HTTP_200_OK),

        (list_all, 'superuser', status.HTTP_200_OK),
        (list_all, 'bucket_admin', status.HTTP_403_FORBIDDEN),
        (list_all, 'normal_user', status.HTTP_403_FORBIDDEN),

        (detail, 'superuser', status.HTTP_200_OK),
        (detail, 'bucket_admin', status.HTTP_200_OK),
        (detail, 'normal_user', status.HTTP_403_FORBIDDEN),

        (create, 'superuser', status.HTTP_302_FOUND),
        (create, 'bucket_admin', status.HTTP_302_FOUND),
        (create, 'normal_user', status.HTTP_302_FOUND),

        (delete, 'superuser', status.HTTP_302_FOUND),
        (delete, 'bucket_admin', status.HTTP_302_FOUND),
        (delete, 'normal_user', status.HTTP_403_FORBIDDEN),
    ],
)
def test_bucket_permissions(client, bucket, users, view, user, expected_status):
    client.force_login(users[user])
    response = view(client, bucket, users)
    assert response.status_code == expected_status


def update_access(client, users3bucket, users, *args):
    data = {
        'user_id': users['bucket_viewer'].auth0_id,
        'access_level': UserS3Bucket.READWRITE,
        'is_admin': False,
    }
    return client.post(
        reverse('update-access-level', kwargs={'pk': users3bucket.id}),
        data,
    )


def revoke_access(client, users3bucket, *args):
    return client.post(
        reverse('revoke-datasource-access', kwargs={'pk': users3bucket.id})
    )


def grant_access(client, users3bucket, users, *args):
    data = {
        'access_level': UserS3Bucket.READWRITE,
        'is_admin': False,
        'user_id': users['other_user'].auth0_id,
    }
    return client.post(
        reverse('grant-datasource-access', kwargs={'pk': users3bucket.s3bucket.id}),
        data,
    )


@pytest.mark.parametrize(
    'view,user,expected_status',
    [
        (update_access, 'superuser', status.HTTP_302_FOUND),
        (update_access, 'bucket_admin', status.HTTP_302_FOUND),
        (update_access, 'normal_user', status.HTTP_403_FORBIDDEN),

        (revoke_access, 'superuser', status.HTTP_302_FOUND),
        (revoke_access, 'bucket_admin', status.HTTP_302_FOUND),
        (revoke_access, 'normal_user', status.HTTP_403_FORBIDDEN),

        (grant_access, 'superuser', status.HTTP_302_FOUND),
        (grant_access, 'bucket_admin', status.HTTP_302_FOUND),
        (grant_access, 'normal_user', status.HTTP_403_FORBIDDEN),
    ],
)
def test_access_permissions(client, users3bucket, users, view, user, expected_status):
    client.force_login(users[user])
    response = view(client, users3bucket, users)
    assert response.status_code == expected_status

