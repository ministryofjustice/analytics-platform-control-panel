# Standard library
import json
from unittest.mock import patch

# Third-party
import pytest
from django.conf import settings
from rest_framework import status
from rest_framework.reverse import reverse

# First-party/Local
from controlpanel.api.models import AppS3Bucket, S3Bucket, UserS3Bucket


@pytest.fixture
def buckets():
    return {
        1: S3Bucket.objects.create(name="test-bucket-1"),
        2: S3Bucket.objects.create(name="test-bucket-2"),
    }


@pytest.fixture
def users3buckets(users, buckets):
    return {
        1: users["normal_user"].users3buckets.create(
            s3bucket=buckets[1],
            access_level=AppS3Bucket.READONLY,
        ),
    }


def test_list(client, users3buckets):
    response = client.get(reverse("users3bucket-list"))
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data["results"]) == 1


def test_detail(client, users3buckets):
    response = client.get(reverse("users3bucket-detail", (users3buckets[1].id,)))
    assert response.status_code == status.HTTP_200_OK

    expected_fields = {"id", "url", "user", "s3bucket", "access_level", "is_admin"}
    assert set(response.data) == expected_fields
    assert response.data["access_level"] == "readonly"


def test_create(client, buckets, users, sqs, helpers):
    data = {
        "user": users["other_user"].auth0_id,
        "s3bucket": buckets[1].id,
        "access_level": AppS3Bucket.READONLY,
    }
    response = client.post(reverse("users3bucket-list"), data)
    assert response.status_code == status.HTTP_201_CREATED

    users3bucket = UserS3Bucket.objects.get(
        user=users["other_user"], s3bucket=buckets[1]
    )
    messages = helpers.retrieve_messages(sqs, settings.IAM_QUEUE_NAME)
    helpers.validate_task_with_sqs_messages(
        messages, UserS3Bucket.__name__, users3bucket.id, settings.IAM_QUEUE_NAME
    )


def test_delete(client, users3buckets):
    with patch(
        "controlpanel.api.models.UserS3Bucket.revoke_bucket_access"
    ) as revoke_bucket_access:
        response = client.delete(reverse("users3bucket-detail", (users3buckets[1].id,)))
        assert response.status_code == status.HTTP_204_NO_CONTENT

        revoke_bucket_access.assert_called()

        response = client.get(reverse("users3bucket-detail", (users3buckets[1].id,)))
        assert response.status_code == status.HTTP_404_NOT_FOUND


def test_update(client, buckets, users, users3buckets, sqs, helpers):
    data = {
        "user": users["normal_user"].auth0_id,
        "s3bucket": buckets[1].id,
        "access_level": UserS3Bucket.READWRITE,
    }
    response = client.put(
        reverse("users3bucket-detail", (users3buckets[1].id,)),
        json.dumps(data),
        content_type="application/json",
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.data["access_level"] == data["access_level"]
    messages = helpers.retrieve_messages(sqs, settings.IAM_QUEUE_NAME)
    users3bucket = UserS3Bucket.objects.get(
        user=users["normal_user"], s3bucket=buckets[1]
    )
    helpers.validate_task_with_sqs_messages(
        messages, UserS3Bucket.__name__, users3bucket.id, settings.IAM_QUEUE_NAME
    )


@pytest.mark.parametrize(
    "user, s3bucket, access_level",
    [
        ("other_user", 1, UserS3Bucket.READWRITE),
        ("normal_user", 2, UserS3Bucket.READWRITE),
    ],
    ids=[
        "app-changed",
        "s3bucket-changed",
    ],
)
def test_update_bad_requests(
    client, buckets, users, users3buckets, user, s3bucket, access_level
):
    response = client.put(
        reverse("users3bucket-detail", (users3buckets[1].id,)),
        json.dumps(
            {
                "user": users[user].auth0_id,
                "s3bucket": buckets[s3bucket].id,
                "access_level": access_level,
            }
        ),
        content_type="application/json",
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
