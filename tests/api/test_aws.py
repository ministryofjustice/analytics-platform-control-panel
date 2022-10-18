# Standard library
import uuid
from unittest.mock import MagicMock, patch

# First-party/Local
from controlpanel.api import aws, cluster
from controlpanel.api.cluster import BASE_ASSUME_ROLE_POLICY, User
from tests.api.fixtures.aws import *


@pytest.yield_fixture(autouse=True)
def enable_db_for_all_tests(db):
    pass


@pytest.yield_fixture(autouse=True)
def app_fixture():
    with patch("tests.api.cluster.test_app.app") as app_fixture:
        yield app_fixture


def stmt_match(
    stmt, Action="sts:AssumeRole", Condition=None, Effect="Allow", Principal={}
):
    result = stmt["Action"] == Action
    if Condition:
        result = result and stmt["Condition"] == Condition
    result = result and stmt["Effect"] == Effect
    result = result and stmt["Principal"] == Principal
    return result


def ec2_assume_role(stmt):
    return stmt_match(stmt, Principal={"Service": "ec2.amazonaws.com"})


def k8s_assume_role(stmt):
    principal = f"arn:aws:iam::{settings.AWS_COMPUTE_ACCOUNT_ID}:role/{settings.K8S_WORKER_ROLE_NAME}"
    if settings.AWS_COMPUTE_ACCOUNT_ID != settings.AWS_DATA_ACCOUNT_ID:
        principal = settings.AWS_COMPUTE_ACCOUNT_ID

    return stmt_match(stmt, Principal={"AWS": principal})


def saml_assume_role(stmt):
    return stmt_match(
        stmt,
        Action="sts:AssumeRoleWithSAML",
        Principal={
            "Federated": f"arn:aws:iam::{settings.AWS_DATA_ACCOUNT_ID}:saml-provider/{settings.SAML_PROVIDER}",
        },
        Condition={
            "StringEquals": {"SAML:aud": "https://signin.aws.amazon.com/saml"},
        },
    )


def oidc_assume_role(stmt, user):
    return stmt_match(
        stmt,
        Action="sts:AssumeRoleWithWebIdentity",
        Principal={
            "Federated": f"arn:aws:iam::{settings.AWS_DATA_ACCOUNT_ID}:oidc-provider/{settings.OIDC_DOMAIN}/",
        },
        Condition={
            "StringEquals": {f"{settings.OIDC_DOMAIN}/:sub": user["auth0_id"]},
        },
    )


def eks_assume_role(stmt, user):
    user_slug = user["user_name"]
    match = f"system:serviceaccount:user-{user_slug}:{user_slug}-*"
    return stmt_match(
        stmt,
        Action="sts:AssumeRoleWithWebIdentity",
        Principal={
            "Federated": f"arn:aws:iam::{settings.AWS_DATA_ACCOUNT_ID}:oidc-provider/{settings.OIDC_EKS_PROVIDER}",
        },
        Condition={
            "StringLike": {f"{settings.OIDC_EKS_PROVIDER}:sub": match},
        },
    )


@pytest.fixture
def roles(iam):
    role_names = [
        "test_app_test-app",
        "test_user_normal-user",
    ]
    for role_name in role_names:
        iam.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(
                {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Effect": "Allow",
                            "Action": "sts:AssumeRole",
                            "Principal": {"Service": "test.amazonaws.com"},
                        }
                    ],
                }
            ),
        )


def test_create_app_role(iam):
    aws.AWSRole().create_role("testing-app", BASE_ASSUME_ROLE_POLICY)

    role = iam.Role("testing-app")
    pd = role.assume_role_policy_document
    assert len(pd["Statement"]) == 2
    assert ec2_assume_role(pd["Statement"][0])
    assert k8s_assume_role(pd["Statement"][1])


def test_create_user_role(iam, managed_policy, airflow_dev_policy, airflow_prod_policy):
    """
    Ensure EKS settngs are in the policy document when running on that
    infrastructure.
    """
    user = {
        "auth0_id": "normal_user",
        "user_name": "testing-bob",
        "iam_role_name": "testing-bob",
    }

    aws.AWSRole().create_role(
        user["iam_role_name"],
        User.aws_user_policy(user["auth0_id"], user["user_name"]),
        User.ATTACH_POLICIES,
    )
    role = iam.Role(user["iam_role_name"])
    pd = role.assume_role_policy_document
    assert len(pd["Statement"]) == 5
    assert ec2_assume_role(pd["Statement"][0])
    assert k8s_assume_role(pd["Statement"][1])
    assert saml_assume_role(pd["Statement"][2])
    assert oidc_assume_role(pd["Statement"][3], user)
    assert eks_assume_role(pd["Statement"][4], user)

    attached_policies = list(role.attached_policies.all())
    assert len(attached_policies) == 3
    arns = [policy.arn for policy in attached_policies]
    assert managed_policy["Arn"] in arns
    assert airflow_dev_policy["Arn"] in arns
    assert airflow_prod_policy["Arn"] in arns


@pytest.mark.parametrize(
    "aws_compute_account_id,aws_data_account_id,expected_principal",
    [
        (
            "test_account_id",
            "test_account_id",
            "arn:aws:iam::test_account_id:role/test_k8s_worker",
        ),
        ("test_compute_account_id", "test_data_account_id", "test_compute_account_id"),
    ],
)
def test_iam_assume_role_principal(
    iam, aws_compute_account_id, aws_data_account_id, expected_principal
):
    with patch("controlpanel.api.aws.settings") as settings_mock:
        settings_mock.AWS_COMPUTE_ACCOUNT_ID = aws_compute_account_id
        settings_mock.AWS_DATA_ACCOUNT_ID = aws_data_account_id
        settings_mock.K8S_WORKER_ROLE_NAME = "test_k8s_worker"

        assert aws.iam_assume_role_principal() == expected_principal


@pytest.fixture
def role_policy():
    def make_role_policy(role):
        policy = role.Policy("test")
        policy.put(
            PolicyDocument=json.dumps(
                {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Action": "s3:ListAllMyBuckets",
                            "Effect": "Allow",
                            "Resource": "arn:aws:s3:::*",
                        }
                    ],
                }
            )
        )
        return policy

    return make_role_policy


# TODO parametrize cases:
#   - role does not exist
def test_delete_role(iam, managed_policy, role_policy):
    user = {
        "auth0_id": "normal_user",
        "user_name": "testing-bob",
        "iam_role_name": "testing-bob",
    }

    aws.AWSRole().create_role(
        user["iam_role_name"],
        User.aws_user_policy(user["auth0_id"], user["user_name"]),
        User.ATTACH_POLICIES,
    )

    role = iam.Role(user["iam_role_name"])
    inline_policy = role_policy(role)

    attached_policy = iam.Policy(managed_policy["Arn"])
    assert attached_policy.attachment_count == 1

    aws.AWSRole().delete_role(user["iam_role_name"])

    with pytest.raises(iam.meta.client.exceptions.NoSuchEntityException):
        role.load()

    with pytest.raises(iam.meta.client.exceptions.NoSuchEntityException):
        inline_policy.load()

    attached_policy.reload()
    assert attached_policy.attachment_count == 0


@pytest.fixture
def logs_bucket(s3):
    bucket = s3.Bucket(settings.LOGS_BUCKET_NAME)
    bucket.create(
        CreateBucketConfiguration={
            "LocationConstraint": settings.BUCKET_REGION,
        }
    )
    bucket.Acl().put(
        AccessControlPolicy={
            "Grants": [
                {
                    "Grantee": {
                        "URI": "http://acs.amazonaws.com/groups/s3/LogDelivery",
                        "Type": "Group",
                    },
                    "Permission": "WRITE",
                },
                {
                    "Grantee": {
                        "Type": "Group",
                        "URI": "http://acs.amazonaws.com/groups/s3/LogDelivery",
                    },
                    "Permission": "READ_ACP",
                },
            ],
            "Owner": bucket.Acl().owner,
        }
    )


def test_create_bucket(logs_bucket, s3):
    bucket_name = f"bucket-{id(MagicMock())}"
    bucket = s3.Bucket(bucket_name)

    with pytest.raises(s3.meta.client.exceptions.NoSuchBucket):
        s3.meta.client.get_bucket_location(Bucket=bucket_name)

    aws.AWSBucket().create_bucket(bucket_name, is_data_warehouse=True)

    # Check versioning.
    assert bucket.Versioning().status == "Enabled"

    # Check lifecycle.
    versioning = bucket.LifecycleConfiguration()
    rule = versioning.rules[0]
    assert rule["ID"].endswith("_lifecycle_configuration")
    assert rule["Status"] == "Enabled"
    assert rule["NoncurrentVersionTransitions"][0]["NoncurrentDays"] == 30
    assert rule["NoncurrentVersionTransitions"][0]["StorageClass"] == "GLACIER"

    # Check logging
    assert bucket.Logging().logging_enabled["TargetBucket"] == settings.LOGS_BUCKET_NAME
    # Check tagging
    tags = {tag["Key"]: tag["Value"] for tag in bucket.Tagging().tag_set}
    assert tags["buckettype"] == "datawarehouse"

    # XXX moto 1.3.10 doesn't provide get_bucket_encryption(),
    # get_public_access_block() or get_bucket_tagging() yet
    # assert encrypted(bucket, alg='AES256')
    # assert public_access_blocked(bucket)


def test_tag_bucket(s3):
    bucket_name = f"bucket-{id(MagicMock())}"
    bucket = s3.Bucket(bucket_name)
    bucket.create()

    aws.AWSBucket().tag_bucket(bucket_name, {"env": "test", "test-update": "old-value"})
    aws.AWSBucket().tag_bucket(
        bucket_name, {"test-update": "new-value", "to-archive": "true"}
    )

    tags = {tag["Key"]: tag["Value"] for tag in bucket.Tagging().tag_set}
    assert tags == {
        "env": "test",
        "test-update": "new-value",
        "to-archive": "true",
    }


def test_create_parameter(ssm):
    aws.AWSParameterStore().create_parameter(
        "test", "test_val", "role_name", description="test desc"
    )

    param = ssm.get_parameter(Name="test", WithDecryption=True)["Parameter"]
    assert param["Value"] == "test_val"

    param = aws.AWSParameterStore().get_parameter(name="test")["Parameter"]
    assert param["Value"] == "test_val"


def test_delete_parameter(ssm):
    aws.AWSParameterStore().delete_parameter("test")

    with pytest.raises(ssm.exceptions.ParameterNotFound):
        ssm.get_parameter(Name="test")


def get_statements_by_sid(policy_document):
    statements = {}
    for statement in policy_document["Statement"]:
        sid = statement.get("Sid")
        if sid:
            statements[sid] = statement
    return statements


@pytest.mark.parametrize(
    "resources",
    [
        ([],),
        (["/foo/bar", "/foo/baz"],),
    ],
    ids=[
        "no-paths",
        "paths",
    ],
)
def test_grant_bucket_access(iam, resources):
    bucket_arn = "arn:aws:s3:::test-bucket"
    path_arns_list = [f"{bucket_arn}{resource}" for resource in resources]
    path_arns_object = [f"{bucket_arn}{resource}/*" for resource in resources]

    user = {
        "auth0_id": "normal_user",
        "user_name": "testing-bob",
        "iam_role_name": "testing-bob",
    }

    aws.AWSRole().create_role(
        user["iam_role_name"],
        User.aws_user_policy(user["auth0_id"], user["user_name"]),
        User.ATTACH_POLICIES,
    )

    aws.AWSRole().grant_bucket_access(
        user["iam_role_name"], bucket_arn, "readonly", path_arns_list
    )

    policy = iam.RolePolicy(user["iam_role_name"], "s3-access")
    statements = get_statements_by_sid(policy.policy_document)

    if path_arns_object:
        assert set(path_arns_object) == set(statements["readonly"]["Resource"])
        assert f"{bucket_arn}/*" not in statements["readonly"]["Resource"]
    else:
        assert set([f"{bucket_arn}/*"]) == set(statements["readonly"]["Resource"])
    # no readwrite statement because no readwrite access granted
    assert "readwrite" not in statements
    assert set([bucket_arn]) == set(statements["list"]["Resource"])

    aws.AWSRole().grant_bucket_access(
        user["iam_role_name"], f"{bucket_arn}-2", "readonly"
    )
    policy.reload()
    statements = get_statements_by_sid(policy.policy_document)
    expected_num_resources = 2
    if path_arns_list:
        expected_num_resources = len(path_arns_list) + 1
    assert len(statements["readonly"]["Resource"]) == expected_num_resources


@pytest.mark.parametrize("resources", [(["/foo/bar", "/foo/baz"],)], ids=["paths"])
def test_revoke_bucket_path_access(iam, resources):
    bucket_arn = "arn:aws:s3:::test-bucket"
    path_arns = [f"{bucket_arn}{resource}" for resource in resources]

    user = {
        "auth0_id": "normal_user",
        "user_name": "testing-bob",
        "iam_role_name": "testing-bob",
    }

    aws.AWSRole().create_role(
        user["iam_role_name"],
        User.aws_user_policy(user["auth0_id"], user["user_name"]),
        User.ATTACH_POLICIES,
    )

    aws.AWSRole().grant_bucket_access(
        user["iam_role_name"], bucket_arn, "readonly", path_arns
    )

    policy = iam.RolePolicy(user["iam_role_name"], "s3-access")

    aws.AWSRole().grant_bucket_access(user["iam_role_name"], bucket_arn, "readonly")
    policy.reload()
    statements = get_statements_by_sid(policy.policy_document)

    assert set([f"{bucket_arn}/*"]) == set(statements["readonly"]["Resource"])
    assert set([f"{bucket_arn}"]) == set(statements["list"]["Resource"])


@pytest.mark.parametrize(
    "resources_1,resources_2",
    [
        (["/foo/bar", "/foo/baz"], ["/foo/bar", "/bar/baz"]),
        (["/foo/bar", "/foo/baz"], ["/bar/foo", "/bar/baz"]),
        (["/foo/bar"], ["/foo/bar", "/foo/baz"]),
    ],
    ids=[
        "change-some-paths",
        "change-all-paths",
        "add-new-paths",
    ],
)
def test_update_bucket_path_access(iam, resources_1, resources_2):
    bucket_arn = "arn:aws:s3:::test-bucket"
    path_arns_list_1 = [f"{bucket_arn}{resource}" for resource in resources_1]
    path_arns_list_2 = [f"{bucket_arn}{resource}" for resource in resources_2]
    path_arns_object_1 = [f"{bucket_arn}{resource}/*" for resource in resources_1]
    path_arns_object_2 = [f"{bucket_arn}{resource}/*" for resource in resources_2]

    user = {
        "auth0_id": "normal_user",
        "user_name": "testing-bob",
        "iam_role_name": "testing-bob",
    }

    aws.AWSRole().create_role(
        user["iam_role_name"],
        User.aws_user_policy(user["auth0_id"], user["user_name"]),
        User.ATTACH_POLICIES,
    )

    aws.AWSRole().grant_bucket_access(
        user["iam_role_name"], bucket_arn, "readonly", path_arns_list_1
    )

    policy = iam.RolePolicy(user["iam_role_name"], "s3-access")
    statements = get_statements_by_sid(policy.policy_document)

    assert set(path_arns_object_1) == set(statements["readonly"]["Resource"])

    aws.AWSRole().grant_bucket_access(
        user["iam_role_name"], bucket_arn, "readonly", path_arns_list_2
    )

    policy.reload()
    statements = get_statements_by_sid(policy.policy_document)

    assert set(path_arns_object_2) == set(statements["readonly"]["Resource"])


@pytest.mark.parametrize(
    "resources",
    [
        ([],),
        (["/foo/bar", "/foo/baz"],),
    ],
    ids=[
        "no-paths",
        "paths",
    ],
)
def test_revoke_bucket_access(iam, resources):
    bucket_arn = "arn:aws:s3:::test-bucket"
    path_arns = [f"{bucket_arn}{resource}" for resource in resources]

    user = {
        "auth0_id": "normal_user",
        "user_name": "testing-bob",
        "iam_role_name": "testing-bob",
    }

    aws.AWSRole().create_role(
        user["iam_role_name"],
        User.aws_user_policy(user["auth0_id"], user["user_name"]),
        User.ATTACH_POLICIES,
    )

    aws.AWSRole().grant_bucket_access(
        user["iam_role_name"], bucket_arn, "readonly", path_arns
    )

    aws.AWSRole().revoke_bucket_access(user["iam_role_name"], bucket_arn)

    policy = iam.RolePolicy(user["iam_role_name"], "s3-access")
    statements = get_statements_by_sid(policy.policy_document)
    assert "readonly" not in statements
    assert "readwrite" not in statements
    assert "list" not in statements


def test_revoke_bucket_access_when_no_role(iam):
    role_name = "test_role_non_existent"
    bucket_arn = "arn:aws:s3:::test-bucket"

    # be sure role doesn't exist before calling revoke_bucket_access()
    with pytest.raises(iam.meta.client.exceptions.NoSuchEntityException):
        role = iam.Role(role_name)
        role.load()

    aws.AWSRole().revoke_bucket_access(role_name, bucket_arn)


def test_create_policy(iam, settings):
    aws.AWSPolicy().create_policy("test", "/group/test/")

    policy = iam.Policy(
        f"arn:aws:iam::{settings.AWS_DATA_ACCOUNT_ID}:policy/group/test/test"
    )
    pd = policy.default_version.document
    stmt = pd["Statement"][0]
    assert stmt["Action"] == [
        "s3:ListAllMyBuckets",
        "s3:ListAccessPoints",
        "s3:GetAccountPublicAccessBlock",
    ]
    assert stmt["Resource"] == "*"
    assert stmt["Effect"] == "Allow"


def assert_group_members(policy, role_names):
    attached_roles = list(policy.attached_roles.all())
    assert len(attached_roles) == len(role_names)
    for role, role_name in zip(attached_roles, role_names):
        assert role.role_name == role_name


@pytest.fixture
def group(iam):
    aws.AWSPolicy().create_policy("test", "/group/test/")
    group_arn = f"arn:aws:iam::{settings.AWS_DATA_ACCOUNT_ID}:policy/group/test/test"
    return iam.Policy(group_arn)


@pytest.mark.parametrize(
    "live, stored",
    [
        ([], ["test_user_alice"]),
        (["test_user_bob"], ["test_user_alice", "test_user_bob"]),
        (["test_user_bob", "test_user_carol"], ["test_user_bob"]),
    ],
    ids=[
        "new-group",
        "add-members",
        "remove-members",
    ],
)
def test_update_policy_members(iam, group, users, live, stored):
    aws.AWSPolicy().update_policy_members(group.arn, set(live))
    assert_group_members(group, live)

    aws.AWSPolicy().update_policy_members(group.arn, set(stored))
    assert_group_members(group, stored)


def test_delete_policy(iam, superuser, group):
    role = iam.Role("test_user_alice")
    aws.AWSPolicy().update_policy_members(group.arn, set([role.name]))

    assert len(list(role.attached_policies.all())) == 4

    try:
        aws.AWSPolicy().delete_policy(group.arn)

    except NotImplementedError as e:
        if "delete_policy" in str(e):
            # moto 1.3.13 doesn't mock delete_policy yet
            pass

    # with pytest.raises(iam.meta.client.exceptions.NoSuchEntityException):
    #     iam.Policy(group_arn).load()

    assert len(list(role.attached_policies.all())) == 3


@pytest.mark.parametrize(
    "resources",
    [
        ([],),
        (["/foo/bar", "/foo/baz"],),
    ],
    ids=[
        "no-paths",
        "paths",
    ],
)
def test_grant_policy_bucket_access(iam, group, resources):
    bucket_arn = "arn:aws:s3:::test-bucket"
    path_arns_list = [f"{bucket_arn}{resource}" for resource in resources]
    path_arns_object = [f"{bucket_arn}{resource}/*" for resource in resources]

    aws.AWSPolicy().grant_policy_bucket_access(
        group.arn, bucket_arn, "readonly", path_arns_list
    )

    group.reload()
    statements = get_statements_by_sid(group.default_version.document)

    if path_arns_object:
        assert set(path_arns_object) == set(statements["readonly"]["Resource"])
        assert f"{bucket_arn}/*" not in statements["readonly"]["Resource"]
    else:
        assert set([f"{bucket_arn}/*"]) == set(statements["readonly"]["Resource"])
    # no readwrite statement because no readwrite access granted
    assert "readwrite" not in statements
    assert set([bucket_arn]) == set(statements["list"]["Resource"])

    aws.AWSPolicy().grant_policy_bucket_access(group.arn, f"{bucket_arn}-2", "readonly")
    group.reload()
    statements = get_statements_by_sid(group.default_version.document)
    expected_num_resources = 2
    if path_arns_list:
        expected_num_resources = len(path_arns_list) + 1
    assert len(statements["readonly"]["Resource"]) == expected_num_resources


@pytest.mark.parametrize(
    "resources",
    [(["/foo/bar", "/foo/baz"],)],
    ids=["paths"],
)
def test_revoke_group_bucket_path_access(iam, group, resources):
    bucket_arn = "arn:aws:s3:::test-bucket"
    path_arns = [f"{bucket_arn}{resource}" for resource in resources]
    aws.AWSPolicy().grant_policy_bucket_access(
        group.arn, bucket_arn, "readonly", path_arns
    )

    aws.AWSPolicy().grant_policy_bucket_access(group.arn, bucket_arn, "readonly")
    group.reload()
    statements = get_statements_by_sid(group.default_version.document)

    assert set([f"{bucket_arn}/*"]) == set(statements["readonly"]["Resource"])
    assert set([f"{bucket_arn}"]) == set(statements["list"]["Resource"])


@pytest.mark.parametrize(
    "resources_1,resources_2",
    [
        (["/foo/bar", "/foo/baz"], ["/foo/bar", "/bar/baz"]),
        (["/foo/bar", "/foo/baz"], ["/bar/foo", "/bar/baz"]),
        (["/foo/bar"], ["/foo/bar", "/foo/baz"]),
    ],
    ids=[
        "change-some-paths",
        "change-all-paths",
        "add-new-paths",
    ],
)
def test_update_policy_bucket_path_access(iam, group, resources_1, resources_2):
    bucket_arn = "arn:aws:s3:::test-bucket"
    path_arns_list_1 = [f"{bucket_arn}{resource}" for resource in resources_1]
    path_arns_list_2 = [f"{bucket_arn}{resource}" for resource in resources_2]
    path_arns_object_1 = [f"{bucket_arn}{resource}/*" for resource in resources_1]
    path_arns_object_2 = [f"{bucket_arn}{resource}/*" for resource in resources_2]

    aws.AWSPolicy().grant_policy_bucket_access(
        group.arn, bucket_arn, "readonly", path_arns_list_1
    )

    group.reload()
    statements = get_statements_by_sid(group.default_version.document)

    assert set(path_arns_object_1) == set(statements["readonly"]["Resource"])

    aws.AWSPolicy().grant_policy_bucket_access(
        group.arn, bucket_arn, "readonly", path_arns_list_2
    )

    group.reload()
    statements = get_statements_by_sid(group.default_version.document)

    assert set(path_arns_object_2) == set(statements["readonly"]["Resource"])


@pytest.mark.parametrize(
    "resources",
    [
        ([],),
        (["/foo/bar", "/foo/baz"],),
    ],
    ids=[
        "no-paths",
        "paths",
    ],
)
def test_revoke_policy_bucket_access(iam, group, resources):
    bucket_arn = "arn:aws:s3:::test-bucket"
    path_arns = [f"{bucket_arn}{resource}" for resource in resources]
    aws.AWSPolicy().grant_policy_bucket_access(
        group.arn, bucket_arn, "readonly", path_arns
    )

    aws.AWSPolicy().revoke_policy_bucket_access(group.arn, bucket_arn)

    group.reload()
    statements = get_statements_by_sid(group.default_version.document)

    assert "readonly" not in statements
    assert "readwrite" not in statements
    assert "list" not in statements


def test_create_app_secret(secretsmanager):
    app_name = "testing_app"
    test_data = {"client_id": "testing_client_id", "client_secret": uuid.uuid4().hex}
    secret_name = "{}_app_secret/{}".format(settings.ENV, app_name)
    aws.AWSSecretManager().create_secret(secret_name, test_data)

    result = secretsmanager.get_secret_value(SecretId=secret_name)
    assert result["Name"] == secret_name
    assert result["SecretString"] == json.dumps(test_data)


@pytest.yield_fixture
def fixture_update_secret():
    with patch("controlpanel.api.aws.AWSSecretManager.update_secret") as update_secret:
        update_secret.return_value = {
            "client_id": "testing_client_id1",
            "ip_ranges": ["1.1.1.1"],
            "client_secret": "testing",
        }
        yield update_secret


def test_update_app_secret(secretsmanager, fixture_update_secret):
    app_name = "testing_app"
    test_data = {"client_id": "testing_client_id", "client_secret": "testing"}
    secret_name = "{}_app_secret/{}".format(settings.ENV, app_name)
    aws.AWSSecretManager().create_secret(secret_name, test_data)

    update_data = {"client_id": "testing_client_id1", "ip_ranges": ["1.1.1.1"]}
    aws.AWSSecretManager().update_secret(secret_name, update_data)

    result = secretsmanager.get_secret_value(SecretId=secret_name)
    assert result["Name"] == secret_name
    fixture_update_secret.assert_called_with(secret_name, update_data)


def test_secret_has_existed_true(secretsmanager):
    app_name = "testing_app"
    test_data = {"client_id": "testing_client_id", "client_secret": uuid.uuid4().hex}
    secret_name = "{}_app_secret/{}".format(settings.ENV, app_name)
    aws.AWSSecretManager().create_secret(secret_name, test_data)

    assert aws.AWSSecretManager().has_existed(secret_name)


def test_secret_has_existed_false(secretsmanager):
    assert not aws.AWSSecretManager().has_existed("Nonexist_secret_name")


def test_delete_app_secret(secretsmanager):
    app_name = "testing_app"
    test_data = {"client_id": "testing_client_id", "client_secret": "testing"}
    secret_name = "{}_app_secret/{}".format(settings.ENV, app_name)
    aws.AWSSecretManager().create_secret(secret_name, test_data)

    result = secretsmanager.get_secret_value(SecretId=secret_name)
    assert result["Name"] == secret_name
    assert result["SecretString"] == json.dumps(test_data)

    aws.AWSSecretManager().delete_secret(secret_name)
    try:
        secretsmanager.get_secret_value(SecretId=secret_name)
        assert False
    except Exception as error:
        if "ResourceNotFoundException" in str(error):
            assert True
        else:
            assert False


def test_delete_key_in_secret(app_fixture):
    app_name = "test_app"
    secret_name = "{}_app_secret/{}".format(settings.ENV, app_name)
    app_fixture.app_aws_secret_name = secret_name
    app_fixture.get_secret_key.return_value = secret_name

    with patch(
        "controlpanel.api.aws.AWSSecretManager.delete_keys_in_secret"
    ) as aws_fixture:
        cluster.App(app_fixture).delete_entries_in_secret(["disable_authentication"])
        aws_fixture.assert_called_with(
            secret_name=secret_name, keys_to_delete=["disable_authentication"]
        )
