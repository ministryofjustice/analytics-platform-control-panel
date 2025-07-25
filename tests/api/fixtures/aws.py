# Standard library
import json
import os

# Third-party
import boto3
import moto
import pytest
from django.conf import settings


@pytest.fixture(autouse=True)
def aws_creds():
    os.environ["AWS_ACCESS_KEY_ID"] = "test-access-key-id"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "test-secret-access-key"
    os.environ["AWS_SECURITY_TOKEN"] = "test-security-token"
    os.environ["AWS_SESSION_TOKEN"] = "test-session-token"


@pytest.fixture(autouse=True)
def iam(aws_creds):
    with moto.mock_aws():
        yield boto3.Session().resource("iam")


@pytest.fixture(autouse=True)
def s3(aws_creds):
    with moto.mock_aws():
        yield boto3.resource("s3")


@pytest.fixture(autouse=True)
def sts(aws_creds):
    with moto.mock_aws():
        yield boto3.client("sts")


@pytest.fixture(autouse=True)
def ssm(aws_creds):
    with moto.mock_aws():
        yield boto3.client("ssm", region_name="eu-west-1")


@pytest.fixture(autouse=True)
def glue(aws_creds):
    with moto.mock_aws():
        glue = boto3.client("glue")
        glue.create_database(DatabaseInput={"Name": settings.DPR_DATABASE_NAME})
        glue.create_table(
            DatabaseName=settings.DPR_DATABASE_NAME,
            TableInput={
                "Name": "test_table",
                "TargetTable": {
                    "CatalogId": "123",
                    "DatabaseName": "external_db",
                    "Name": "external_test_table",
                    "Region": "eu-west-2",
                },
            },
        )
        yield glue


@pytest.fixture(autouse=True)
def lake_formation(aws_creds):
    with moto.mock_aws():
        lake_formation = boto3.client("lakeformation")
        lake_formation.grant_permissions(
            Permissions=["DESCRIBE"],
            Principal={
                "DataLakePrincipalIdentifier": "arn:aws:iam::123456789012:role/test_user_carol"
            },
            Resource={
                "Table": {
                    "CatalogId": "123456789012",
                    "DatabaseName": "test_database",
                    "Name": "test_table",
                },
            },
        )
        lake_formation.grant_permissions(
            Permissions=["SELECT"],
            Principal={
                "DataLakePrincipalIdentifier": "arn:aws:iam::123456789012:role/test_user_carol"
            },
            Resource={
                "Table": {
                    "CatalogId": "123",
                    "DatabaseName": "external_db",
                    "Name": "external_test_table",
                },
            },
        )

        yield lake_formation


@pytest.fixture(autouse=True)
def sqs(aws_creds):
    with moto.mock_aws():
        sqs = boto3.resource("sqs")
        sqs.create_queue(QueueName=settings.DEFAULT_QUEUE)
        sqs.create_queue(QueueName=settings.IAM_QUEUE_NAME)
        sqs.create_queue(QueueName=settings.S3_QUEUE_NAME)
        yield sqs


@pytest.fixture(autouse=True)
def secretsmanager(aws_creds):
    with moto.mock_aws():
        yield boto3.client("secretsmanager", region_name="eu-west-1")


@pytest.fixture(autouse=True)
def managed_policy(iam):
    result = iam.meta.client.create_policy(
        PolicyName="test-read-user-roles-inline-policies",
        PolicyDocument=json.dumps(
            {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Sid": "CanReadUserRolesInlinePolicies",
                        "Effect": "Allow",
                        "Action": ["iam:GetRolePolicy"],
                        "Resource": [
                            "arn:aws:iam::{settings.AWS_DATA_ACCOUNT_ID}:role/{settings.ENV}_user_*"  # noqa: E501
                        ],
                    },
                ],
            }
        ),
    )
    return result["Policy"]


@pytest.fixture(autouse=True)
def airflow_dev_policy(iam):
    policy_name = "airflow-dev-ui-access"
    result = iam.meta.client.create_policy(
        PolicyName=policy_name,
        PolicyDocument=json.dumps(
            {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Sid": "ManagedAirflowCreateWebLoginToken",
                        "Effect": "Allow",
                        "Action": ["iam:CreateWebLoginToken"],
                        "Resource": [
                            "arn:aws:iam::{settings.AWS_DATA_ACCOUNT_ID}:role/{settings.ENV}_user_*"  # noqa: E501
                        ],
                    },
                ],
            }
        ),
    )
    return result["Policy"]


@pytest.fixture(autouse=True)
def airflow_prod_policy(iam):
    policy_name = "airflow-prod-ui-access"
    result = iam.meta.client.create_policy(
        PolicyName=policy_name,
        PolicyDocument=json.dumps(
            {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Sid": "ManagedAirflowCreateWebLoginToken",
                        "Effect": "Allow",
                        "Action": ["iam:CreateWebLoginToken"],
                        "Resource": [
                            "arn:aws:iam::{settings.AWS_DATA_ACCOUNT_ID}:role/{settings.ENV}_user_*"  # noqa: E501
                        ],
                    },
                ],
            }
        ),
    )
    return result["Policy"]


@pytest.fixture(autouse=True)
def bedrock_policy(iam):
    result = iam.meta.client.create_policy(
        PolicyName="analytical-platform-bedrock-integration",
        PolicyDocument=json.dumps(
            {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Sid": "BedrockEnable",
                        "Effect": "Allow",
                        "Action": ["iam:AllowBedrock"],
                        "Resource": [
                            "arn:aws:iam::{settings.AWS_DATA_ACCOUNT_ID}:role/{settings.ENV}_user_*"  # noqa: E501
                        ],
                    },
                ],
            }
        ),
    )
    return result["Policy"]


@pytest.fixture(autouse=True)
def textract_policy(iam):
    result = iam.meta.client.create_policy(
        PolicyName="analytical-platform-textract-integration",
        PolicyDocument=json.dumps(
            {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Sid": "TextractEnable",
                        "Effect": "Allow",
                        "Action": ["iam:AllowTextract"],
                        "Resource": [
                            "arn:aws:iam::{settings.AWS_DATA_ACCOUNT_ID}:role/{settings.ENV}_user_*"  # noqa: E501
                        ],
                    },
                ],
            }
        ),
    )
    return result["Policy"]


@pytest.fixture(autouse=True)
def comprehend_policy(iam):
    result = iam.meta.client.create_policy(
        PolicyName="analytical-platform-comprehend-integration",
        PolicyDocument=json.dumps(
            {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Sid": "ComprehendEnable",
                        "Effect": "Allow",
                        "Action": ["iam:AllowComprehend"],
                        "Resource": [
                            "arn:aws:iam::{settings.AWS_DATA_ACCOUNT_ID}:role/{settings.ENV}_user_*"  # noqa: E501
                        ],
                    },
                ],
            }
        ),
    )
    return result["Policy"]


@pytest.fixture(autouse=True)
def test_policy(iam):
    result = iam.meta.client.create_policy(
        PolicyName="a-test-policy",
        PolicyDocument=json.dumps(
            {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Sid": "ThisIsATestPolicy",
                        "Effect": "Allow",
                        "Action": ["iam:TestPolicy"],
                        "Resource": [
                            "arn:aws:iam::{settings.AWS_DATA_ACCOUNT_ID}:role/{settings.ENV}_user_*"  # noqa: E501
                        ],
                    },
                ],
            }
        ),
    )
    return result["Policy"]


@pytest.fixture(autouse=True)
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


@pytest.fixture()
def root_folder_bucket(s3):
    yield s3.create_bucket(
        Bucket=settings.S3_FOLDER_BUCKET_NAME,
        CreateBucketConfiguration={
            "LocationConstraint": settings.BUCKET_REGION,  # noqa: F405
        },
    )


@pytest.fixture(autouse=True)
def quicksight(aws_creds):
    with moto.mock_aws():
        yield boto3.client("quicksight", region_name="eu-west-1")


@pytest.fixture(autouse=True)
def sso_admin(aws_creds):
    with moto.mock_aws():
        yield boto3.client("sso-admin", region_name="eu-west-2")


@pytest.fixture(autouse=True)
def identity_store_id(sso_admin):
    response = sso_admin.list_instances()
    yield response["Instances"][0]["IdentityStoreId"]


@pytest.fixture(autouse=True)
def identity_store(aws_creds):
    with moto.mock_aws():
        client = boto3.client("identitystore", region_name="eu-west-2")
        yield client


@pytest.fixture
def group_ids(identity_store_id, identity_store):
    group_ids = {}

    group_ids["quicksight_compute_reader"] = identity_store.create_group(
        IdentityStoreId=identity_store_id, DisplayName=settings.QUICKSIGHT_READER_GROUP_NAME
    )["GroupId"]
    group_ids["quicksight_compute_author"] = identity_store.create_group(
        IdentityStoreId=identity_store_id, DisplayName=settings.QUICKSIGHT_AUTHOR_GROUP_NAME
    )["GroupId"]
    group_ids["azure_holding"] = identity_store.create_group(
        IdentityStoreId=identity_store_id, DisplayName=settings.AZURE_HOLDING_GROUP_NAME
    )["GroupId"]

    yield group_ids


@pytest.fixture
def identity_store_user_setup(users, identity_store_id, group_ids, identity_store):

    for key, user in users.items():
        if user.justice_email is not None:
            forename, surname = user.justice_email.split("@")[0].split(".")
            response = identity_store.create_user(
                IdentityStoreId=identity_store_id,
                UserName=user.justice_email,
                DisplayName=user.justice_email,
                Name={
                    "FamilyName": surname,
                    "GivenName": forename,
                },
                Emails=[{"Value": user.justice_email, "Type": "EntraId", "Primary": True}],
            )
            user.identity_center_id = response["UserId"]

            if user.is_superuser:
                identity_store.create_group_membership(
                    IdentityStoreId=identity_store_id,
                    GroupId=group_ids["azure_holding"],
                    MemberId={"UserId": user.identity_center_id},
                )

                response = identity_store.create_group_membership(
                    IdentityStoreId=identity_store_id,
                    GroupId=group_ids["quicksight_compute_author"],
                    MemberId={"UserId": user.identity_center_id},
                )

                user.group_membership_id = response["MembershipId"]

            if key in group_ids:
                identity_store.create_group_membership(
                    IdentityStoreId=identity_store_id,
                    GroupId=group_ids["azure_holding"],
                    MemberId={"UserId": user.identity_center_id},
                )

                response = identity_store.create_group_membership(
                    IdentityStoreId=identity_store_id,
                    GroupId=group_ids[key],
                    MemberId={"UserId": user.identity_center_id},
                )

                user.group_membership_id = response["MembershipId"]
