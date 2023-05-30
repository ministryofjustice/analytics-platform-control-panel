# Standard library
from unittest.mock import call, patch

# Third-party
import pytest
from botocore.exceptions import ClientError
from model_mommy import mommy

# First-party/Local
from controlpanel.api.models import S3Bucket, UserS3Bucket


@pytest.fixture(autouse=True)
def enable_db_access_for_all_tests(db):
    pass


@pytest.fixture
def bucket():
    return S3Bucket.objects.create(name="test-bucket-1")


def test_delete_revokes_permissions(bucket):
    with patch("controlpanel.api.aws.AWSRole.grant_bucket_access"), \
            patch("controlpanel.api.cluster.AWSRole.revoke_bucket_access") \
            as revoke_bucket_access_action:
        users3bucket = mommy.make("api.UserS3Bucket", s3bucket=bucket)
        apps3bucket = mommy.make("api.AppS3Bucket", s3bucket=bucket)

        bucket.delete()

        revoke_bucket_access_action.assert_has_calls(
            [
                call(apps3bucket.iam_role_name, bucket.arn),
                call(users3bucket.iam_role_name, bucket.arn),
            ]
        )


def test_delete_marks_bucket_for_archival(bucket):
    with patch("controlpanel.api.cluster.AWSBucket.tag_bucket") as tag_bucket:
        bucket.delete()
        tag_bucket.assert_called_once_with(bucket.name, {"to-archive": "true"})


def test_delete_marks_bucket_for_archival_when_tag_bucket_fails(bucket):
    with patch("controlpanel.api.cluster.AWSBucket.tag_bucket") as tag_bucket:
        tag_bucket.side_effect = ClientError({"error": "true"}, "TagFailed")
        with pytest.raises(ClientError):
            bucket.delete()

        # The S3 bucket record is not deleted from the DB
        assert S3Bucket.objects.filter(name=bucket.name).exists()


def test_bucket_create():
    with patch("controlpanel.api.cluster.AWSBucket.create_bucket") as create_bucket:
        bucket = S3Bucket.objects.create(name="test-bucket-1")
        create_bucket.assert_called_with(bucket.name, False)


def test_create_users3bucket(superuser):
    with patch("controlpanel.api.cluster.AWSBucket.create_bucket") as create_bucket:
        bucket = S3Bucket.objects.create(
            name="test-bucket-1",
            created_by=superuser,
        )

        create_bucket.assert_called()

        assert UserS3Bucket.objects.get(user=superuser, s3bucket=bucket)


@pytest.mark.parametrize(
    "name,expected",
    [
        ("bucketname/foldername", True),
        ("bucketname", False),
    ],
)
def test_is_folder(name, expected):
    assert S3Bucket(name=name).is_folder is expected
