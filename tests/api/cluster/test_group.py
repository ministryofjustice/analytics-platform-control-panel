from model_mommy import mommy
import pytest
from unittest.mock import patch
from controlpanel.api import cluster


@pytest.fixture(autouse=True)
def enable_db_for_all_tests(db):
    pass


@pytest.fixture
def iam_managed_policy():
    return mommy.make('api.IAMManagedPolicy', name='test')


def test_arn(settings, iam_managed_policy):
    assert cluster.RoleGroup(iam_managed_policy).arn == (
        f"arn:aws:iam::{settings.AWS_DATA_ACCOUNT_ID}:policy/{settings.ENV}/group/test"
    )


@pytest.yield_fixture
def aws_create_policy():
    with patch('controlpanel.api.cluster.AWSPolicy.create_policy') as aws_create_policy_action:
        yield aws_create_policy_action


def test_create(aws_create_policy, iam_managed_policy):
    cluster.RoleGroup(iam_managed_policy).create()
    aws_create_policy.assert_called_with(
        iam_managed_policy.name,
        iam_managed_policy.path,
    )

