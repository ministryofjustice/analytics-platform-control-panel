import json

import pytest
from rest_framework import status
from rest_framework.reverse import reverse

from controlpanel.api.models import (
    AppS3Bucket,
    S3Bucket,
    UserS3Bucket,
)


@pytest.fixture
def buckets():
    return {
        1: S3Bucket.objects.create(name="test-bucket-1"),
        2: S3Bucket.objects.create(name="test-bucket-2"),
    }


@pytest.fixture
def users3buckets(users, buckets):
    return {
        1: users[1].users3buckets.create(
            s3bucket=buckets[1],
            access_level=AppS3Bucket.READONLY,
        ),
    }


def test_list(client, users3buckets):
    response = client.get(reverse('users3bucket-list'))
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data['results']) == 1


def test_detail(client, users3buckets):
    response = client.get(reverse('users3bucket-detail', (users3buckets[1].id,)))
    assert response.status_code == status.HTTP_200_OK

    expected_fields = {
        'id',
        'url',
        'user',
        's3bucket',
        'access_level',
        'is_admin'
    }
    assert set(response.data) == expected_fields
    assert response.data['access_level'] == 'readonly'


def test_create(client, buckets, users, aws):
    data = {
        'user': users[2].auth0_id,
        's3bucket': buckets[1].id,
        'access_level': AppS3Bucket.READONLY,
    }
    response = client.post(reverse('users3bucket-list'), data)
    assert response.status_code == status.HTTP_201_CREATED

    aws.put_role_policy.assert_called()
    # TODO get policy from call and assert bucket ARN exists


def test_delete(client, users3buckets, aws):
    response = client.delete(reverse('users3bucket-detail', (users3buckets[1].id,)))
    assert response.status_code == status.HTTP_204_NO_CONTENT

    aws.put_role_policy.assert_called()
    # TODO get policy from call and assert bucket ARN not contained

    response = client.get(reverse('users3bucket-detail', (users3buckets[1].id,)))
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_update(client, buckets, users, users3buckets, aws):
    data = {
        'user': users[1].auth0_id,
        's3bucket': buckets[1].id,
        'access_level': UserS3Bucket.READWRITE,
    }
    response = client.put(
        reverse('users3bucket-detail', (users3buckets[1].id,)),
        json.dumps(data),
        content_type="application/json",
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.data['access_level'] == data['access_level']

    aws.put_role_policy.assert_called()
    # TODO get policy and assert ARN present in correct place


@pytest.mark.parametrize(
    "user, s3bucket, access_level",
    [
        (2, 1, UserS3Bucket.READWRITE),
        (1, 2, UserS3Bucket.READWRITE),
    ],
    ids=[
        'app-changed',
        's3bucket-changed',
    ]
)
def test_update_bad_requests(
        client, buckets, users, users3buckets, user, s3bucket, access_level):
    response = client.put(
        reverse('users3bucket-detail', (users3buckets[1].id,)),
        json.dumps({
            "user": users[user].auth0_id,
            "s3bucket": buckets[s3bucket].id,
            "access_level": access_level,
        }),
        content_type="application/json",
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
