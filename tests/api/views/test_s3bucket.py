# Standard library
import json
from unittest.mock import patch

# Third-party
import pytest
from botocore.exceptions import ClientError
from django.conf import settings
from model_bakery import baker
from rest_framework import status
from rest_framework.reverse import reverse

# First-party/Local
from controlpanel.api.models import S3Bucket, UserS3Bucket
from tests.api.fixtures.es import BUCKET_HITS_AGGREGATION


@pytest.fixture
def bucket():
    with patch("controlpanel.api.aws.AWSBucket.create"):
        return baker.make("api.S3Bucket", name="test-bucket-1")


@pytest.fixture(autouse=True)
def models(bucket):
    with patch("controlpanel.api.aws.AWSRole.grant_bucket_access"), \
            patch("controlpanel.api.aws.AWSBucket.create"):
        baker.make("api.S3Bucket")
        baker.make("api.S3Bucket", is_data_warehouse=True)
        baker.make("api.AppS3Bucket", s3bucket=bucket)
        baker.make("api.UserS3Bucket", s3bucket=bucket)


def test_list(client):
    response = client.get(reverse("s3bucket-list"))
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data["results"]) == 3

    response = client.get(reverse("s3bucket-list") + "?is_data_warehouse=true")
    assert len(response.data["results"]) == 1


def test_detail(client, bucket):
    response = client.get(reverse("s3bucket-detail", (bucket.id,)))
    assert response.status_code == status.HTTP_200_OK

    expected_s3bucket_fields = {
        "id",
        "url",
        "name",
        "arn",
        "apps3buckets",
        "users3buckets",
        "created_by",
        "is_data_warehouse",
        "location_url",
        "is_deleted",
        "deleted_by",
        "deleted_at",
    }
    assert set(response.data) == expected_s3bucket_fields

    apps3bucket = response.data["apps3buckets"][0]
    expected_apps3bucket_fields = {"id", "url", "app", "access_level"}
    assert set(apps3bucket) == expected_apps3bucket_fields

    expected_app_fields = {
        "id",
        "url",
        "name",
        "description",
        "slug",
        "repo_url",
        "iam_role_name",
        "created_by",
    }
    assert set(apps3bucket["app"]) == expected_app_fields

    users3bucket = response.data["users3buckets"][0]
    expected_users3bucket_fields = {"id", "user", "access_level", "is_admin"}
    assert set(users3bucket) == expected_users3bucket_fields

    expected_user_fields = {
        "auth0_id",
        "url",
        "username",
        "name",
        "email",
    }
    assert set(users3bucket["user"]) == expected_user_fields


def test_delete(client, bucket):
    response = client.delete(reverse("s3bucket-detail", (bucket.id,)))
    assert response.status_code == status.HTTP_204_NO_CONTENT

    response = client.get(reverse("s3bucket-detail", (bucket.id,)))
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_create(client, superuser, sqs, helpers):
    data = {"name": "test-bucket-123"}
    response = client.post(reverse("s3bucket-list"), data)
    assert response.status_code == status.HTTP_201_CREATED

    assert response.data["created_by"] == superuser.auth0_id
    assert not response.data["is_data_warehouse"]

    # create_bucket.assert_called()

    bucket = S3Bucket.objects.get(id=response.data["id"])
    users3bucket = UserS3Bucket.objects.get(
        user_id=superuser.auth0_id,
        s3bucket_id=response.data["id"],
    )

    assert users3bucket.user.auth0_id == superuser.auth0_id
    assert response.data["id"] == users3bucket.s3bucket.id
    assert UserS3Bucket.READWRITE == users3bucket.access_level
    assert users3bucket.is_admin

    s3_messages = helpers.retrieve_messages(sqs, queue_name=settings.S3_QUEUE_NAME)
    helpers.validate_task_with_sqs_messages(
        s3_messages, S3Bucket.__name__, bucket.id, queue_name=settings.S3_QUEUE_NAME
    )
    iam_messages = helpers.retrieve_messages(sqs, queue_name=settings.IAM_QUEUE_NAME)
    helpers.validate_task_with_sqs_messages(
        iam_messages, UserS3Bucket.__name__, users3bucket.id, queue_name=settings.IAM_QUEUE_NAME
    )


EXISTING_BUCKET_NAME = object()


@pytest.mark.parametrize(
    "name",
    [
        EXISTING_BUCKET_NAME,
        "ab",
        "127.0.0.1",
        "__test_bucket__",
        "badenv-bucketname",
        "bucketname",
    ],
    ids=[
        "name-exists",
        "name-too-short",
        "name-like-ipaddr",
        "name-invalid-start-end-chars",
        "name-invalid-prefix",
        "name-no-prefix",
    ],
)
def test_create_bad_request(client, bucket, name):
    if name is EXISTING_BUCKET_NAME:
        name = bucket.name
    response = client.post(reverse("s3bucket-list"), {"name": name})
    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_update(client, bucket):
    data = {"name": "test-bucket-updated"}
    response = client.put(
        reverse("s3bucket-detail", (bucket.id,)),
        json.dumps(data),
        content_type="application/json",
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.data["name"] == data["name"]


@pytest.mark.skip(reason="Needs to move to test_aws")
def test_aws_error_existing_ignored(client, aws):
    e = type("BucketAlreadyOwnedByYou", (ClientError,), {})
    aws.create_bucket.side_effect = e({}, "Foo")

    data = {"name": "test-bucket-123"}
    response = client.post(reverse("s3bucket-list"), data)
    assert response.status_code == status.HTTP_201_CREATED

    aws.create_bucket.assert_called()


def test_access_logs(client, bucket, elasticsearch):
    elasticsearch.search.return_value = BUCKET_HITS_AGGREGATION

    response = client.get(reverse("s3bucket-access-logs", (bucket.id,)))
    assert response.status_code == status.HTTP_200_OK

    assert len(response.data) == 2

    assert response.data[0]["accessed_by"] == "sentencing-policy-model"
    assert response.data[0]["count"] == 11
    assert response.data[0]["type"] == "app"

    assert response.data[1]["accessed_by"] == "foobar"
    assert response.data[1]["count"] == 3
    assert response.data[1]["type"] == "user"
