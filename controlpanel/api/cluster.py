import json
import logging

from django.conf import settings

from controlpanel.api.aws import aws, iam_arn
from controlpanel.api.helm import helm


log = logging.getLogger(__name__)


BASE_ROLE_POLICY = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {
                "Service": "ec2.amazonaws.com",
            },
            "Action": "sts:AssumeRole",
        },
        {
            "Effect": "Allow",
            "Principal": {
                "AWS": iam_arn(f"role/{settings.K8S_WORKER_ROLE_NAME}"),
            },
            "Action": "sts:AssumeRole",
        },
    ],
}

CONSOLE_STATEMENT = {
    "Sid": "console",
    "Action": [
        "s3:GetBucketLocation",
        "s3:ListAllMyBuckets",
    ],
    "Effect": "Allow",
    "Resource": ["arn:aws:s3:::*"],
}

OIDC_STATEMENT = {
    "Effect": "Allow",
    "Principal": {
        "Federated": iam_arn(f"oidc-provider/{settings.OIDC_DOMAIN}"),
    },
    "Action": "sts:AssumeRoleWithWebIdentity",
}

READ_INLINE_POLICIES = f'{settings.ENV}-read-user-roles-inline-policies'

SAML_STATEMENT = {
    "Effect": "Allow",
    "Principal": {
        "Federated": iam_arn(f"saml-provider/{settings.SAML_PROVIDER}"),
    },
    "Action": "sts:AssumeRoleWithSAML",
    "Condition": {
        "StringEquals": {
            "SAML:aud": "https://signin.aws.amazon.com/saml",
        },
    },
}


def is_ignored_exception(e):
    ignored_exception_names = (
        'BucketAlreadyOwnedByYou',
        'EntityAlreadyExistsException',
        'NoSuchEntityException',
    )
    if e.__class__.__name__ in ignored_exception_names:
        log.error(f"Caught AWS exception and ignored: {e}")
        return True


def initialize_user(user):
    role = IAMRole(user.iam_role_name)
    role.allow_assume_role_with_saml()
    role.allow_assume_role_with_oidc(sub=user.auth0_id)
    role.save()

    aws.attach_policy_to_role(
        role_name=user.iam_role_name,
        policy_arn=iam_arn(f"policy/{READ_INLINE_POLICIES}"),
    )

    helm.upgrade_release(
        f"init-user-{user.slug}",
        "mojanalytics/init-user",
        f"--set=" + (
            f"Env={settings.ENV},"
            f"NFSHostname={settings.NFS_HOSTNAME},"
            f"OidcDomain={settings.OIDC_DOMAIN},"
            f"Email={user.email},"
            f"Fullname={user.name},"
            f"Username={user.slug}"
        ),
    )
    helm.upgrade_release(
        f"config-user-{user.slug}",
        "mojanalytics/config-user",
        "--namespace=user-{user.slug}",
        "--set=Username={user.slug}",
    )


def purge_user(user):
    aws.delete_role(user.iam_role_name)
    helm.delete(helm.list_releases(f"--namespace=user-{user.slug}"))
    helm.delete(f"init-user-{user.slug}")


def create_app_role(name):
    role = IAMRole(name)
    role.save()


def delete_app_role(name):
    try:
        aws.delete_role(name)
    except Exception as e:
        if not is_ignored_exception(e):
            raise e


class IAMRole:

    def __init__(self, role_name):
        self.policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {
                        "Service": "ec2.amazonaws.com",
                    },
                    "Action": "sts:AssumeRole",
                },
                {
                    "Effect": "Allow",
                    "Principal": {
                        "AWS": iam_arn(f"role/{settings.K8S_WORKER_ROLE_NAME}"),
                    },
                    "Action": "sts:AssumeRole",
                },
            ],
        }
        self.role_name = role_name

    def save(self):
        try:
            aws.create_role(self.role_name, self.policy)
        except Exception as e:
            if not is_ignored_exception(e):
                raise e

    def allow_assume_role_with_saml(self):
        self.policy["Statement"].append(dict(SAML_STATEMENT))

    def allow_assume_role_with_oidc(self, sub):
        stmt = dict(OIDC_STATEMENT)
        stmt["Condition"] = {
            "StringEquals": {
                f"{settings.OIDC_DOMAIN}/:sub": sub,
            }
        }
        self.policy["Statement"].append(stmt)


class S3AccessPolicy(dict):
    POLICY_NAME = "s3-access"

    def __init__(self, role_name=None, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.role_name = role_name
        self._ro = set()
        self._rw = set()

        for statement in self.get("Statement", []):
            sid = statement.get("Sid")

            if sid == "readonly":
                self._ro = set([
                    arn.rstrip('/*')
                    for arn in statement["Resource"]
                ])

            elif sid == "readwrite":
                self._rw = set([
                    arn.rstrip('/*')
                    for arn in statement["Resource"]
                ])

    @classmethod
    def load(cls, role_name):
        document = aws.get_inline_policy_document(
            role_name=role_name,
            policy_name=cls.POLICY_NAME,
        )
        policy = cls(role_name=role_name, **document)
        return policy

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.save()
        return True

    def save(self):
        aws.put_role_policy(
            self.role_name,
            policy_name=self.POLICY_NAME,
            policy_document=self,
        )

    def _update_statements(self):
        self["Statement"] = [
            CONSOLE_STATEMENT,
            self.list_statement(self._ro | self._rw),
            self.readonly_statement(self._ro),
            self.readwrite_statement(self._rw),
        ]

    def grant_access(self, bucket_arn, access_level="readonly"):
        if access_level in ("readonly", "readwrite"):
            if access_level == "readwrite":
                self._ro.discard(bucket_arn)
                self._rw.add(bucket_arn)
            elif access_level == "readonly":
                self._ro.add(bucket_arn)
                self._rw.discard(bucket_arn)
            self._update_statements()

    def revoke_access(self, bucket_arn):
        self._rw.discard(bucket_arn)
        self._ro.discard(bucket_arn)
        self._update_statements()

    def list_statement(self, resources):
        return {
            "Sid": "list",
            "Action": [
                "s3:ListBucket",
            ],
            "Effect": "Allow",
            "Resource": list(resources),
        }

    def readonly_statement(self, resources):
        return {
            "Sid": "readonly",
            "Action": [
                "s3:GetObject",
                "s3:GetObjectAcl",
                "s3:GetObjectVersion",
            ],
            "Effect": "Allow",
            "Resource": [
                f"{arn}/*"
                for arn in resources
            ],
        }

    def readwrite_statement(self, resources):
        statement = self.readonly_statement(resources)
        statement["Sid"] = "readwrite"
        statement["Action"].extend([
            "s3:DeleteObject",
            "s3:DeleteObjectVersion",
            "s3:PutObject",
            "s3:PutObjectAcl",
            "s3:RestoreObject",
        ])
        return statement


def create_bucket(bucket_name, is_data_warehouse=False):
    try:
        result = aws.create_bucket(
            bucket_name,
            region=settings.BUCKET_REGION,
            acl='private',
        )
        aws.put_bucket_logging(
            bucket_name,
            target_bucket=settings.LOGS_BUCKET_NAME,
            target_prefix=f"{bucket_name}/",
        )
        aws.put_bucket_encryption(bucket_name)

        if is_data_warehouse:
            aws.put_bucket_tagging(
                bucket_name,
                tags={'buckettype': 'datawarehouse'},
            )

        return result

    except Exception as e:
        if not is_ignored_exception(e):
            raise e
