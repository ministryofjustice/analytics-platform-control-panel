"S3Bucket permissions tests"

# Standard library
import json

# Third-party
import pytest
from model_mommy import mommy
from rest_framework import status
from rest_framework.reverse import reverse

# First-party/Local
import controlpanel.api.rules  # noqa: F401
from controlpanel.api.models import S3Bucket, UserS3Bucket


@pytest.fixture
def users(users):
    for i, role in enumerate(("viewer", "editor", "admin")):
        users.update(
            {
                f"bucket_{role}": mommy.make(
                    "api.User",
                    username=role,
                    auth0_id=f"github|user_{5 + i}",
                ),
            }
        )
    return users


@pytest.fixture
def bucket(users):
    bucket = S3Bucket.objects.create(name="test-bucket-1")
    UserS3Bucket.objects.create(
        user=users["bucket_viewer"],
        s3bucket=bucket,
        access_level=UserS3Bucket.READONLY,
    )
    UserS3Bucket.objects.create(
        user=users["bucket_editor"],
        s3bucket=bucket,
        access_level=UserS3Bucket.READWRITE,
    )
    UserS3Bucket.objects.create(
        user=users["bucket_admin"],
        s3bucket=bucket,
        access_level=UserS3Bucket.READWRITE,
        is_admin=True,
    )
    return bucket


def bucket_list(client, *args):
    return client.get(reverse("s3bucket-list"))


def bucket_detail(client, bucket, *args):
    return client.get(reverse("s3bucket-detail", (bucket.id,)))


def bucket_delete(client, bucket, *args):
    return client.delete(reverse("s3bucket-detail", (bucket.id,)))


def bucket_create(client, *args):
    data = {
        "name": "test-bucket",
    }
    return client.post(
        reverse("s3bucket-list"),
        json.dumps(data),
        content_type="application/json",
    )


def bucket_update(client, bucket, users, *args):
    data = {
        "name": bucket.name,
    }
    return client.put(
        reverse("s3bucket-detail", (bucket.id,)),
        json.dumps(data),
        content_type="application/json",
    )


@pytest.mark.parametrize(
    "view,user,expected_status",
    [
        (bucket_list, "superuser", status.HTTP_200_OK),
        (bucket_detail, "superuser", status.HTTP_200_OK),
        (bucket_delete, "superuser", status.HTTP_204_NO_CONTENT),
        (bucket_create, "superuser", status.HTTP_201_CREATED),
        (bucket_update, "superuser", status.HTTP_200_OK),
        (bucket_list, "normal_user", status.HTTP_200_OK),
        (bucket_detail, "normal_user", status.HTTP_404_NOT_FOUND),
        (bucket_delete, "normal_user", status.HTTP_404_NOT_FOUND),
        (bucket_create, "normal_user", status.HTTP_201_CREATED),
        (bucket_update, "normal_user", status.HTTP_404_NOT_FOUND),
        (bucket_list, "bucket_viewer", status.HTTP_200_OK),
        (bucket_detail, "bucket_viewer", status.HTTP_200_OK),
        (bucket_delete, "bucket_viewer", status.HTTP_403_FORBIDDEN),
        (bucket_create, "bucket_viewer", status.HTTP_201_CREATED),
        (bucket_update, "bucket_viewer", status.HTTP_403_FORBIDDEN),
        (bucket_list, "bucket_editor", status.HTTP_200_OK),
        (bucket_detail, "bucket_editor", status.HTTP_200_OK),
        (bucket_delete, "bucket_editor", status.HTTP_403_FORBIDDEN),
        (bucket_create, "bucket_editor", status.HTTP_201_CREATED),
        (bucket_update, "bucket_editor", status.HTTP_200_OK),
        (bucket_list, "bucket_admin", status.HTTP_200_OK),
        (bucket_detail, "bucket_admin", status.HTTP_200_OK),
        (bucket_delete, "bucket_admin", status.HTTP_204_NO_CONTENT),
        (bucket_create, "bucket_admin", status.HTTP_201_CREATED),
        (bucket_update, "bucket_admin", status.HTTP_200_OK),
    ],
)
@pytest.mark.django_db
def test_permission(client, bucket, users, view, user, expected_status):
    client.force_login(users[user])
    response = view(client, bucket, users)
    assert response.status_code == expected_status
