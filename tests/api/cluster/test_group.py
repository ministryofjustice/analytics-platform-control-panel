from model_mommy import mommy
import pytest

from controlpanel.api import cluster


@pytest.fixture(autouse=True)
def enable_db_for_all_tests(db):
    pass


@pytest.fixture
def iam_managed_policy():
    return mommy.make('api.IAMManagedPolicy', name='test')


def test_arn(settings, iam_managed_policy):
    assert cluster.Group(iam_managed_policy).arn == (
        f'arn:aws:iam::{settings.AWS_ACCOUNT_ID}:policy/{settings.ENV}/group/test'
    )


def test_create(aws, iam_managed_policy):
    cluster.Group(iam_managed_policy).create()
    aws.create_group_policy.assert_called_with(
        iam_managed_policy.name,
        iam_managed_policy.path,
    )

