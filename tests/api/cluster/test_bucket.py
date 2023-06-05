# Standard library
from unittest.mock import patch, PropertyMock, MagicMock

# Third-party
import pytest
from model_mommy import mommy

# First-party/Local
from controlpanel.api import cluster, aws


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
        "controlpanel.api.aws.AWSBucket.create"
    ) as aws_create_bucket_action:
        yield aws_create_bucket_action


@pytest.yield_fixture
def aws_create_folder():
    with patch(
        "controlpanel.api.aws.AWSFolder.create"
    ) as aws_create_folder_action:
        yield aws_create_folder_action


@pytest.yield_fixture
def aws_tag_bucket():
    with patch(
        "controlpanel.api.cluster.AWSBucket.tag_bucket"
    ) as aws_tag_bucket_action:
        yield aws_tag_bucket_action


@pytest.mark.parametrize(
    "is_folder, aws_service_fixture",
    [
        (False, "aws_create_bucket"),
        (True, "aws_create_folder"),
    ]
)
def test_aws_create(is_folder, aws_service_fixture, bucket, request):
    with patch.object(
        bucket.__class__, "is_folder", new_callable=PropertyMock(return_value=is_folder)
    ):
        aws_bucket_service = request.getfixturevalue(aws_service_fixture)
        cluster.S3Bucket(bucket).create()
        aws_bucket_service.assert_called_with(bucket.name, False)


def test_mark_for_archival(aws_tag_bucket, bucket):
    cluster.S3Bucket(bucket).mark_for_archival()
    aws_tag_bucket.assert_called_with(bucket.name, {"to-archive": "true"})


@pytest.mark.parametrize(
    "bucket, expected",
    [
        (MagicMock(spec=["is_folder"], is_folder=True), aws.AWSFolder),
        (MagicMock(spec=["is_folder"], is_folder=False), aws.AWSBucket),
        (None, aws.AWSBucket),
    ]
)
def test_init_correct_service(bucket, expected):
    obj = cluster.S3Bucket(bucket)
    assert isinstance(obj.aws_bucket_service, expected)
