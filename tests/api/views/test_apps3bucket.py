# Standard library
import json
from unittest.mock import patch

# Third-party
import pytest
from model_mommy import mommy
from rest_framework import status
from rest_framework.reverse import reverse

# First-party/Local
from controlpanel.api.models import AppS3Bucket, S3Bucket


@pytest.fixture
def apps():
    return {
        1: mommy.make("api.App", name="app_1"),
        2: mommy.make("api.App", name="app_2"),
    }


@pytest.fixture
def buckets():
    return {
        1: S3Bucket.objects.create(name="test-bucket-1"),
        2: S3Bucket.objects.create(name="test-bucket-2"),
        3: S3Bucket.objects.create(name="test-bucket-3"),
    }


@pytest.fixture
def apps3buckets(apps, buckets):
    with patch("controlpanel.api.aws.AWSRole.grant_bucket_access"):
        return {
            1: apps[1].apps3buckets.create(
                s3bucket=buckets[1],
                access_level=AppS3Bucket.READONLY,
            ),
            2: apps[2].apps3buckets.create(
                s3bucket=buckets[2],
                access_level=AppS3Bucket.READONLY,
            ),
        }


def test_list(client, apps3buckets):
    response = client.get(reverse("apps3bucket-list"))
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data["results"]) == 2


def test_detail(client, apps3buckets):
    response = client.get(reverse("apps3bucket-detail", (apps3buckets[1].id,)))
    assert response.status_code == status.HTTP_200_OK

    expected_fields = {"id", "url", "app", "s3bucket", "access_level"}
    assert set(response.data) == expected_fields


def test_delete(client, apps3buckets):
    with patch(
        "controlpanel.api.models.AppS3Bucket.revoke_bucket_access"
    ) as revoke_bucket_access:
        response = client.delete(reverse("apps3bucket-detail", (apps3buckets[1].id,)))
        assert response.status_code == status.HTTP_204_NO_CONTENT

        revoke_bucket_access.assert_called()

        response = client.get(reverse("apps3bucket-detail", (apps3buckets[1].id,)))
        assert response.status_code == status.HTTP_404_NOT_FOUND


def test_create(client, apps, buckets, sqs, helpers):
    data = {
        "app": apps[1].id,
        "s3bucket": buckets[3].id,
        "access_level": AppS3Bucket.READONLY,
    }
    response = client.post(reverse("apps3bucket-list"), data)
    assert response.status_code == status.HTTP_201_CREATED
    apps3bucket = AppS3Bucket.objects.get(app=apps[1], s3bucket=buckets[3])
    messages = helpers.retrieve_messages(sqs)
    helpers.validate_task_with_sqs_messages(
        messages, AppS3Bucket.__name__, apps3bucket.id
    )


def test_update(client, apps, apps3buckets, buckets, sqs, helpers):
    data = {
        "app": apps[1].id,
        "s3bucket": buckets[1].id,
        "access_level": AppS3Bucket.READWRITE,
    }
    response = client.put(
        reverse("apps3bucket-detail", (apps3buckets[1].id,)),
        json.dumps(data),
        content_type="application/json",
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.data["access_level"] == data["access_level"]
    apps3bucket = AppS3Bucket.objects.get(app=apps[1], s3bucket=buckets[1])
    messages = helpers.retrieve_messages(sqs)
    helpers.validate_task_with_sqs_messages(
        messages, AppS3Bucket.__name__, apps3bucket.id
    )


def test_update_bad_requests(client, apps, apps3buckets, buckets):
    fixtures = (
        {
            "app": apps[2].id,  # when app changed
            "s3bucket": buckets[1].id,
            "access_level": AppS3Bucket.READWRITE,
        },
        {
            "app": apps[1].id,  # when s3bucket changed
            "s3bucket": buckets[2].id,
            "access_level": AppS3Bucket.READWRITE,
        },
    )

    for data in fixtures:
        response = client.put(
            reverse("apps3bucket-detail", (apps3buckets[1].id,)),
            json.dumps(data),
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_create_with_s3_data_warehouse_not_allowed(client, apps):
    with patch("controlpanel.api.aws.AWSRole.grant_bucket_access"), \
            patch("controlpanel.api.aws.AWSBucket.create"):
        s3_bucket_app = mommy.make(
            "api.S3Bucket",
            is_data_warehouse=False,
        )

        data = {
            "app": apps[1].id,
            "s3bucket": s3_bucket_app.id,
            "access_level": AppS3Bucket.READONLY,
        }
        response = client.post(reverse("apps3bucket-list"), data)
        assert response.status_code == status.HTTP_201_CREATED

        s3_bucket = mommy.make("api.S3Bucket", is_data_warehouse=True)

        data = {
            "app": apps[1].id,
            "s3bucket": s3_bucket.id,
            "access_level": AppS3Bucket.READONLY,
        }
        response = client.post(reverse("apps3bucket-list"), data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
