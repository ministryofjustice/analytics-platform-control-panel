import pytest

import json
from copy import deepcopy
from typing import Any
from controlpanel.api import aws
from tests.api.fixtures.aws import *
from controlpanel.api.aws import S3AccessPolicy
from controlpanel.api.cluster import BASE_ASSUME_ROLE_POLICY, User
from controlpanel.api.dtos.folders import FolderCheck, get_folder

@pytest.fixture(autouse=True)
def bucket_settings(settings):
    # override django settings
    settings.MAIN_BUCKET_FOLDER = 'test-bucket'


class TestMock:
    def __init__(self, policy):
        self.policy_document = policy


def test_policy_change(iam, managed_policy, bucket_settings):
    user = {
        "auth0_id": "normal_user",
        "user_name": "testing-bob",
        "iam_role_name": "testing-bob",
    }
    bucket_arn = "arn:aws:s3:::test-bucket"

    policy_default = User.aws_user_policy(user["auth0_id"], user["user_name"])

    pol_mock = TestMock(policy_default)
    policy = S3AccessPolicy(deepcopy(pol_mock))

    folder_arn1 = f'{bucket_arn}/halo'
    folder_name = get_folder(folder_arn1, bucket_arn)

    policy.grant_object_access(folder_arn1, "readwrite")
    folder_arn2 = f'{bucket_arn}/red'
    policy.grant_object_access(folder_arn2, "readwrite")

    folder_arn3 = f'{bucket_arn}/halo/red'
    policy.grant_object_access(folder_arn3, "readwrite")

    policy.revoke_access(folder_arn1)
    assert policy.policy_document != policy_default


@pytest.mark.parametrize(
    "to_insert, existing, expected, is_parent",
    [
        ('/halo/token', '/halo/*', True, False),
        ('/halo', '/halo/*', True, True),
        ('/halo/token/roman', '/halo/*/roman/*', True, False),
        ('/halo/goldfish/exo/rex/*', '/halo/*/exo/*/gamma/*', True, False),
    ]
)
def test_relative_folders(existing, to_insert, expected, is_parent):
    to_insertx = FolderCheck(to_insert)
    check_against = FolderCheck(existing)
    result = to_insertx.is_child(check_against)
    assert result == expected
    if is_parent:
        assert to_insertx.is_parent(check_against) == expected
