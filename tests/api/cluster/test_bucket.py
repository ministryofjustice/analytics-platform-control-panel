# Standard library
from unittest.mock import patch

# Third-party
import pytest
from model_mommy import mommy

# First-party/Local
from controlpanel.api import cluster


@pytest.fixture(autouse=True)
def enable_db_for_all_tests(db):
    pass


@pytest.fixture
def bucket():
    return mommy.prepare("api.S3Bucket", name="test-bucket")


def test_arn(bucket):
    assert cluster.S3Bucket(bucket).arn == "arn:aws:s3:::test-bucket"


@pytest.yield_fixture
def aws_create_bucket():
    with patch(
        "controlpanel.api.cluster.AWSBucket.create_bucket"
    ) as aws_create_bucket_action:
        yield aws_create_bucket_action


@pytest.yield_fixture
def aws_tag_bucket():
    with patch(
        "controlpanel.api.cluster.AWSBucket.tag_bucket"
    ) as aws_tag_bucket_action:
        yield aws_tag_bucket_action


def test_create(aws_create_bucket, bucket):
    cluster.S3Bucket(bucket).create()
    aws_create_bucket.assert_called_with(bucket.name, False)


def test_mark_for_archival(aws_tag_bucket, bucket):
    cluster.S3Bucket(bucket).mark_for_archival()
    aws_tag_bucket.assert_called_with(bucket.name, {"to-archive": "true"})
