from model_mommy import mommy
import pytest

from controlpanel.api.cluster import (
    App,
    RoleGroup,
    S3Bucket,
    User,
)

@pytest.fixture(autouse=True)
def enable_db_for_all_tests(db):
    pass


@pytest.fixture
def bucket():
    return mommy.make('api.S3Bucket')


@pytest.fixture
def entities(bucket, users):
    return {
        'app': App(mommy.make('api.App')),
        'group': RoleGroup(mommy.make('api.IAMManagedPolicy')),
        'user': User(users['normal_user']),
    }


@pytest.mark.parametrize(
    'entity_type, resources',
    [
        ('app', []),
        ('app', ['/foo/bar', '/foo/baz']),
        ('user', []),
        ('user', ['/foo/bar', '/foo/baz']),
    ],
    ids=[
        'app',
        'app-paths',
        'user',
        'user-paths',
    ],
)
def test_grant_access(aws, bucket, entities, entity_type, resources):
    entity = entities[entity_type]
    entity.grant_bucket_access(bucket.arn, 'readonly', resources)

    aws.grant_bucket_access.assert_called_with(
        entity.iam_role_name,
        bucket.arn,
        'readonly',
        resources,
    )


@pytest.mark.parametrize(
    'resources',
    [
        ([]),
        (['/foo/bar', '/foo/baz']),
    ],
    ids=[
        'group',
        'group-paths',
    ],
)
def test_grant_group_access(aws, bucket, entities, resources):
    entity = entities['group']
    entity.grant_bucket_access(bucket.arn, 'readonly', resources)

    aws.grant_group_bucket_access.assert_called_with(
        entity.arn,
        bucket.arn,
        'readonly',
        resources,
    )

