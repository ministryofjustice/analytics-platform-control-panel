# Standard library
from unittest.mock import patch

# Third-party
import pytest
from model_mommy import mommy

# First-party/Local
from controlpanel.api.cluster import App, RoleGroup, User


@pytest.fixture
def grant_bucket_access():
    with patch(
        "controlpanel.api.cluster.AWSRole.grant_bucket_access"
    ) as grant_bucket_access_action:
        yield grant_bucket_access_action


@pytest.fixture
def grant_folder_access():
    with patch(
        "controlpanel.api.cluster.AWSRole.grant_folder_access"
    ) as grant_bucket_access_action:
        yield grant_bucket_access_action


@pytest.fixture
def grant_policy_bucket_access():
    with patch(
        "controlpanel.api.cluster.AWSPolicy.grant_policy_bucket_access"
    ) as grant_policy_bucket_access_action:
        yield grant_policy_bucket_access_action


@pytest.fixture(autouse=True)
def enable_db_for_all_tests(db):
    pass


@pytest.fixture
def bucket():
    return mommy.prepare("api.S3Bucket")


@pytest.fixture
def entities(bucket, users):
    return {
        "app": App(mommy.prepare("api.App")),
        "group": RoleGroup(mommy.prepare("api.IAMManagedPolicy")),
        "user": User(users["normal_user"]),
    }


@pytest.mark.parametrize(
    "entity_type, resources",
    [
        ("app", []),
        ("app", ["/foo/bar", "/foo/baz"]),
        ("user", []),
        ("user", ["/foo/bar", "/foo/baz"]),
    ],
    ids=[
        "app",
        "app-paths",
        "user",
        "user-paths",
    ],
)
def test_grant_access(grant_bucket_access, bucket, entities, entity_type, resources):
    entity = entities[entity_type]
    entity.grant_bucket_access(bucket.arn, "readonly", resources)

    grant_bucket_access.assert_called_with(
        entity.iam_role_name,
        bucket.arn,
        "readonly",
        resources,
    )


@pytest.mark.parametrize(
    "entity_type, resources",
    [
        ("user", []),
        ("user", ["/foo/bar", "/foo/baz"]),
    ],
    ids=[
        "user",
        "user-paths",
    ],
)
def test_grant_folder_access(grant_folder_access, bucket, entities, entity_type, resources):
    entity = entities[entity_type]
    entity.grant_folder_access(bucket.arn, "readonly", resources)

    grant_folder_access.assert_called_with(
        role_name=entity.iam_role_name,
        bucket_arn=bucket.arn,
        access_level="readonly",
        paths=resources,
    )


@pytest.mark.parametrize(
    "resources",
    [
        ([]),
        (["/foo/bar", "/foo/baz"]),
    ],
    ids=[
        "group",
        "group-paths",
    ],
)
def test_grant_group_access(grant_policy_bucket_access, bucket, entities, resources):
    entity = entities["group"]
    entity.grant_bucket_access(bucket.arn, "readonly", resources)

    grant_policy_bucket_access.assert_called_with(
        entity.arn,
        bucket.arn,
        "readonly",
        resources,
    )
