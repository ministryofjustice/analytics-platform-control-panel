# Standard library
from unittest.mock import patch

# Third-party
import pytest
from django.conf import settings
from model_bakery import baker

# First-party/Local
from controlpanel.api import cluster
from controlpanel.api.cluster import AWSRoleCategory


@pytest.fixture(autouse=True)
def enable_db_for_all_tests(db):
    pass


@pytest.fixture
def bucket():
    return baker.prepare("api.S3Bucket", name="test-bucket")


def test_arn(bucket):
    assert cluster.S3Bucket(bucket).arn == "arn:aws:s3:::test-bucket"


@pytest.fixture
def aws_create_bucket():
    with patch(
        "controlpanel.api.aws.AWSBucket.create"
    ) as aws_create_bucket_action:
        yield aws_create_bucket_action


@pytest.fixture
def aws_create_folder():
    with patch(
        "controlpanel.api.aws.AWSFolder.create"
    ) as aws_create_folder_action:
        yield aws_create_folder_action


@pytest.fixture
def aws_tag_bucket():
    with patch(
        "controlpanel.api.cluster.AWSBucket.tag_bucket"
    ) as aws_tag_bucket_action:
        yield aws_tag_bucket_action


@pytest.mark.parametrize(
    "cluster_class, aws_service_fixture",
    [
        (cluster.S3Bucket, "aws_create_bucket"),
        (cluster.S3Folder, "aws_create_folder"),
    ]
)
def test_aws_create(cluster_class, aws_service_fixture, bucket, request):
    aws_bucket_service = request.getfixturevalue(aws_service_fixture)
    cluster_class(bucket).create()
    aws_bucket_service.assert_called_with(bucket.name, False)


def test_mark_for_archival(aws_tag_bucket, bucket):
    cluster.S3Bucket(bucket).mark_for_archival()
    aws_tag_bucket.assert_called_with(bucket.name, {"to-archive": "true"})


def test_aws_folder_exists(bucket):
    with patch("controlpanel.api.aws.AWSFolder.exists") as mock_exists:
        mock_exists.return_value = False
        result = cluster.S3Folder(None).exists(bucket.name, AWSRoleCategory.user)
        folder_path = f"{settings.S3_FOLDER_BUCKET_NAME}/{bucket.name}"
        mock_exists.assert_called_once_with(folder_path)
        assert result == (False, folder_path)
