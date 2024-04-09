# Third-party
import pytest
from model_bakery import baker
from rest_framework import status
from rest_framework.reverse import reverse


@pytest.fixture(autouse=True)
def enable_db_for_all_tests(db):
    pass


@pytest.fixture(autouse=True)
def buckets(db):
    return {
        1: baker.make("api.S3Bucket", name="test-bucket-1"),
        2: baker.make("api.S3Bucket", name="test-bucket-2"),
    }


@pytest.fixture(autouse=True)
def users3bucket(db, buckets, users):
    return baker.make(
        "api.UserS3Bucket",
        user=users["normal_user"],
        s3bucket=buckets[1],
        access_level="readonly",
        is_admin=False,
    )


def test_superuser_sees_everything(client, buckets, users):
    client.force_login(users["superuser"])

    response = client.get(reverse("s3bucket-list"))

    s3_bucket_ids = [b["id"] for b in response.data["results"]]
    assert len(s3_bucket_ids) == 2
    assert buckets[1].id in s3_bucket_ids
    assert buckets[2].id in s3_bucket_ids


def test_normal_user_sees_only_buckets_has_access_to(client, buckets, users):
    client.force_login(users["normal_user"])

    response = client.get(reverse("s3bucket-list"))
    assert response.status_code == status.HTTP_200_OK

    s3_bucket_ids = [b["id"] for b in response.data["results"]]
    assert buckets[1].id in s3_bucket_ids
    assert buckets[2].id not in s3_bucket_ids
