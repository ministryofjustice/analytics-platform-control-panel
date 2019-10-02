from model_mommy import mommy
import pytest

from controlpanel.api import cluster


@pytest.fixture(autouse=True)
def enable_db_for_all_tests(db):
    pass


@pytest.fixture
def bucket():
    return mommy.make('api.S3Bucket', name='test-bucket')


def test_arn(bucket):
    assert cluster.Bucket(bucket).arn == 'arn:aws:s3:::test-bucket'


def test_create(aws, bucket):
    cluster.Bucket(bucket).create()
    aws.create_bucket.assert_called_with(bucket.name, False)
