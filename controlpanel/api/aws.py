# Standard library
import base64
import hashlib
import json
import re
from copy import deepcopy
from typing import Optional

# Third-party
import botocore
import structlog
from django.conf import settings

# First-party/Local
from controlpanel.api.aws_auth import AWSCredentialSessionSet

log = structlog.getLogger(__name__)


def arn(service, resource, region="", account=""):
    service = service.lower()
    region = region.lower()
    regionless = ["iam", "s3"]
    if service in regionless:
        region = ""

    return f"arn:aws:{service}:{region}:{account}:{resource}"


def s3_arn(resource):
    return arn("s3", resource)


def iam_arn(resource, account=settings.AWS_DATA_ACCOUNT_ID):
    return arn("iam", resource, account=account)


READ_ACTIONS = [
    "s3:GetObject",
    "s3:GetObjectAcl",
    "s3:GetObjectVersion",
    "s3:GetObjectVersionAcl",
    "s3:GetObjectVersionTagging",
]

WRITE_ACTIONS = [
    "s3:DeleteObject",
    "s3:DeleteObjectVersion",
    "s3:PutObject",
    "s3:PutObjectAcl",
    "s3:RestoreObject",
]

LIST_BUCKET_META_ACTIONS = [
    "s3:GetBucketPublicAccessBlock",
    "s3:GetBucketPolicyStatus",
    "s3:GetBucketTagging",
    "s3:GetBucketPolicy",
    "s3:GetBucketAcl",
    "s3:GetBucketCORS",
    "s3:GetBucketVersioning",
    "s3:GetBucketLocation",
    "s3:ListBucketVersions",
]

LIST_BUCKET_CONTENTS_ACTIONS = [
    "s3:ListBucket",
]

LIST_ACTIONS = LIST_BUCKET_META_ACTIONS + LIST_BUCKET_CONTENTS_ACTIONS


BASE_S3_ACCESS_STATEMENT = {
    "list": {
        "Sid": "list",
        "Action": LIST_ACTIONS,
        "Effect": "Allow",
    },
    "readonly": {
        "Sid": "readonly",
        "Action": READ_ACTIONS,
        "Effect": "Allow",
    },
    "readwrite": {
        "Sid": "readwrite",
        "Action": READ_ACTIONS + WRITE_ACTIONS,
        "Effect": "Allow",
    },
    # additional permissions for folder based access
    "listFolder": {
        "Sid": "listFolder",
        "Action": LIST_BUCKET_CONTENTS_ACTIONS,
        "Effect": "Allow",
    },
    "listSubFolders": {
        "Sid": "listSubFolders",
        "Action": [
            "s3:ListBucket",
        ],
        "Effect": "Allow",
    },
    "rootFolderBucketMeta": {
        "Sid": "rootFolderBucketMeta",
        "Action": LIST_BUCKET_META_ACTIONS,
        "Effect": "Allow",
    },
}

BUCKET_TLS_STATEMENT = {
    "Sid": "DenyInsecureTransport",
    "Action": "s3:*",
    "Effect": "Deny",
    "Principal": "*",
    "Resource": ["arn:aws:s3:::{bucket_arn}", "arn:aws:s3:::{bucket_arn}/*"],
    "Condition": {"Bool": {"aws:SecureTransport": "false"}},
}

BASE_S3_ACCESS_POLICY = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "ListUserBuckets",
            "Action": [
                "s3:ListAllMyBuckets",
                "s3:ListAccessPoints",
                "s3:GetAccountPublicAccessBlock",
            ],
            "Effect": "Allow",
            "Resource": "*",
        },
    ],
}


class S3AccessPolicy:
    """Provides a convenience wrapper around a RolePolicy object"""

    SID_SUFFIX_LEN = 32

    def __init__(self, policy):
        self.policy = policy
        self.statements = {}

        try:
            self.policy_document = self.load_policy_document()

        except self.policy.meta.client.exceptions.NoSuchEntityException:
            # create an empty s3 access policy
            self.policy_document = deepcopy(BASE_S3_ACCESS_POLICY)
            self.put(policy_document=self.policy_document)

        # ensure version is set
        self.policy_document["Version"] = "2012-10-17"

        # ensure statements are correctly configured and build a lookup table
        self.policy_document.setdefault("Statement", [])
        for stmt in self.policy_document["Statement"]:
            sid = stmt.get("Sid")
            if sid in self.base_s3_access_sids:
                stmt.update(deepcopy(BASE_S3_ACCESS_STATEMENT[sid]))
                self.statements[sid] = stmt
                continue

            # check for the SID without md5 suffix
            if sid[: -self.SID_SUFFIX_LEN] in self.base_s3_access_sids:
                stmt.update(deepcopy(BASE_S3_ACCESS_STATEMENT[sid[: -self.SID_SUFFIX_LEN]]))
                stmt["Sid"] = sid
                self.statements[sid] = stmt

    @property
    def base_s3_access_sids(self):
        return [statement["Sid"] for key, statement in BASE_S3_ACCESS_STATEMENT.items()]

    def load_policy_document(self):
        # triggers API call
        return self.policy.policy_document

    def _build_statement(self, base_sid, sid):
        """
        Build and store a new statement dictionary copied from the
        BASE_S3_ACCESS_STATEMENT.
        If a suffix is given this is appended to the Sid of the new statement block.
        """
        statement = deepcopy(BASE_S3_ACCESS_STATEMENT[base_sid])
        statement["Sid"] = sid
        self.statements[sid] = statement
        self.policy_document["Statement"].append(statement)
        return statement

    @staticmethod
    def _construct_sid(base_sid, suffix=None):
        """
        If a suffix is given this is used to create a md5 hash in order to meet AWS
        requirements for the Sid, which supports only uppercase letters (A-Z), lowercase
        letters (a-z), and numbers (0-9).
        """
        if not suffix:
            return base_sid

        suffix = hashlib.md5(suffix.encode()).hexdigest()
        return f"{base_sid}{suffix}"

    def statement(self, base_sid, suffix=None):
        """
        Get or build the statement element for the given Sid and suffix.

        :param str base_sid: should be one of the Sid defined that are defined in the
        BASE_S3_ACCESS_STATEMENT
        :param suffix: Optional arg, if given will be used when constructing the Sid
        that is used to lookup or build a statement element.
        :type suffix: str or None
        """
        if base_sid not in self.base_s3_access_sids:
            return

        sid = self._construct_sid(base_sid, suffix)
        statement = self.statements.get(sid, None)
        if not statement:
            statement = self._build_statement(base_sid=base_sid, sid=sid)

        return statement

    def add_resource(self, arn, sid, sid_suffix=None):
        statement = self.statement(sid, sid_suffix)
        if statement:
            statement["Resource"] = statement.get("Resource", [])
            if arn not in statement["Resource"]:
                statement["Resource"].append(arn)

    def _is_arn_part_of_resource(self, resource, arn):
        """In general, the partition letter for path is / , but in some of occasions,
        it will have other parts, e.g. in moto (the python package for mocking
        aws service), somehow add [] at the end of bucket
        e.g. arn:aws:s3:::test-bucket[]/* which is strange.
        This function is to make the check more general based on the bucket
        convention rules
        https://docs.aws.amazon.com/AmazonS3/latest/userguide/bucketnamingrules.html
        """
        if resource.startswith(arn):
            if len(resource) > len(arn):
                end_char = resource[len(arn)]
                return not re.match("^[a-z0-9-.]$", end_char)
            else:
                return True
        return False

    def remove_prefix(self, root_folder_path, sid, condition):
        """
        Remove the folder name from the prefixes condition of a statement block. The
        prefixes condition is used to limit list access to specific folders in an S3
        bucket, so by removing the folder name from the prefixes it removes access to
        that folder.

        :param str root_folder_path: Path to the root folder including bucket name e.g.
        user-data-bucket/my-folder
        :param str sid: Statement ID
        :param str condition: Condition operator. Should be StringEquals or StringLike
        """
        # split the path into the bucket name and the folder name
        bucket_name, folder = self.get_bucket_and_path(root_folder_path)
        statement = self.statement(sid, suffix=bucket_name)
        if not statement:
            return

        # build arn for the bucket to check that it is included in the statements
        # resource element
        bucket_arn = s3_arn(resource=bucket_name)
        if bucket_arn not in statement.get("Resource", []):
            return

        try:
            prefixes = statement["Condition"][condition]["s3:prefix"]
        except KeyError:
            prefixes = []

        # remove access to the folder
        prefixes[:] = [prefix for prefix in prefixes if not prefix.startswith(folder)]

        # remove the resource if no prefixes left so that the statement is removed
        if prefixes == [] or prefixes == [""]:
            statement.pop("Resource", None)

    def remove_resource(self, arn, sid):
        statement = self.statement(sid)
        if statement:
            resources = statement.get("Resource", [])
            for resource in list(resources):
                # Make sure the resource can be removed only when the arn is part
                # of paths of the resource
                if self._is_arn_part_of_resource(resource, arn):
                    resources.remove(resource)

    def grant_object_access(self, arn, access_level):
        self.add_resource(f"{arn}/*", access_level)

    def grant_list_access(self, arn):
        self.add_resource(arn, "list")

    def _add_folder_to_list_folder_prefixes(self, folder, bucket_name):
        statement = self.statement("listFolder", suffix=bucket_name)
        # make sure that we are updating statement for the correct bucket
        if s3_arn(bucket_name) not in statement["Resource"]:
            return

        try:
            prefixes = statement["Condition"]["StringEquals"]["s3:prefix"]
        except KeyError:
            prefixes = [""]

        subfolders = folder.split("/")[:-1]
        for index, path in enumerate(subfolders):
            prev = "/".join(subfolders[:index])
            if prev:
                path = f"{prev}/{path}"

            if path not in prefixes:
                prefixes.append(path)
                prefixes.append(f"{path}/")

        if folder not in prefixes:
            prefixes.append(folder)

        statement["Condition"] = {"StringEquals": {"s3:prefix": prefixes, "s3:delimiter": ["/"]}}

    def _add_folder_to_list_sub_folders_prefixes(self, folder, bucket_name):
        statement = self.statement("listSubFolders", suffix=bucket_name)

        # make sure that we are updating statement for the correct bucket
        if s3_arn(bucket_name) not in statement["Resource"]:
            return

        try:
            prefixes = statement["Condition"]["StringLike"]["s3:prefix"]
        except KeyError:
            prefixes = []

        folder_wildcard = f"{folder}/*"
        if folder_wildcard not in prefixes:
            prefixes.append(folder_wildcard)

        statement["Condition"] = {"StringLike": {"s3:prefix": prefixes}}

    @staticmethod
    def get_bucket_and_path(folder_path):
        """
        Splits a path on the first / to return the name of the bucket and rest of
        the path.
        """
        return folder_path.split("/", 1)

    def grant_folder_access(self, root_folder_path, access_level, paths=None):
        """
        Grant access to the given folder for the given access level. If paths have been
        specified, only grants access to those paths within the root folder.
        """
        bucket_name, folder = self.get_bucket_and_path(root_folder_path)
        bucket_arn = s3_arn(bucket_name)
        # make sure the root bucket arn is included in the resources
        self.add_resource(bucket_arn, "rootFolderBucketMeta")
        self.add_resource(bucket_arn, "listFolder", sid_suffix=bucket_name)
        self.add_resource(bucket_arn, "listSubFolders", sid_suffix=bucket_name)

        folder_paths = [folder]
        if paths:
            folder_paths = [f"{folder}{path}" for path in paths]

        for folder_path in folder_paths:
            self.grant_object_access(
                arn=f"{bucket_arn}/{folder_path}",
                access_level=access_level,
            )
            self._add_folder_to_list_folder_prefixes(folder_path, bucket_name)
            self._add_folder_to_list_sub_folders_prefixes(folder_path, bucket_name)

    def revoke_access(self, arn):
        self.remove_resource(arn, "readonly")
        self.remove_resource(arn, "readwrite")
        self.remove_resource(arn, "list")

    def revoke_folder_access(self, root_folder_path):
        # build arn for full path, including the folder name. important to include the
        # folder name, as this is the resource string that is used when granting access
        bucket_name, _ = self.get_bucket_and_path(root_folder_path)
        folder_resource_arn = s3_arn(root_folder_path)
        self.remove_resource(arn=folder_resource_arn, sid="readonly")
        self.remove_resource(arn=folder_resource_arn, sid="readwrite")
        self.remove_resource(arn=s3_arn(bucket_name), sid="rootFolderBucketMeta")
        self.remove_prefix(
            root_folder_path=root_folder_path,
            sid="listFolder",
            condition="StringEquals",
        )
        self.remove_prefix(
            root_folder_path=root_folder_path,
            sid="listSubFolders",
            condition="StringLike",
        )

    def put(self, policy_document=None):
        if policy_document is None:
            policy_document = self.policy_document

        # remove statements with no resources
        policy_document["Statement"][:] = [
            stmt for stmt in policy_document["Statement"] if stmt.get("Resource")
        ]

        return self.save_policy_document(policy_document)

    def save_policy_document(self, policy_document):
        return self.policy.put(
            PolicyDocument=json.dumps(policy_document),
        )


class ManagedS3AccessPolicy(S3AccessPolicy):
    """Provides a convenience wrapper around a Policy object"""

    def load_policy_document(self):
        return self.policy.default_version.document

    def save_policy_document(self, policy_document):
        self.policy.create_version(
            PolicyDocument=json.dumps(policy_document),
            SetAsDefault=True,
        )

        for version in self.policy.versions.all():
            if version.version_id != self.policy.default_version_id:
                version.delete()

        return self


class AWSService:
    def __init__(self, assume_role_name=None, profile_name=None, region_name=None):
        self.assume_role_name = assume_role_name
        self.profile_name = profile_name
        self.region_name = region_name or settings.AWS_DEFAULT_REGION

        self.aws_sessions = AWSCredentialSessionSet()

    @property
    def boto3_session(self):
        log.info(
            f"Get boto3 session with assume_role_name: {self.assume_role_name}, profile_name: {self.profile_name}, region_name: {self.region_name}"  # noqa
        )
        return self.aws_sessions.get_session(
            assume_role_name=self.assume_role_name,
            profile_name=self.profile_name,
            region_name=self.region_name,
        )


class AWSRole(AWSService):
    def create_role(self, iam_role_name, role_policy, attach_policies: list = None):
        iam = self.boto3_session.resource("iam")
        try:
            iam.create_role(
                RoleName=iam_role_name,
                AssumeRolePolicyDocument=json.dumps(role_policy),
            )
            role = iam.Role(iam_role_name)
            for attach_policy in attach_policies or []:
                role.attach_policy(
                    PolicyArn=iam_arn(f"policy/{attach_policy}"),
                )
        except iam.meta.client.exceptions.EntityAlreadyExistsException:
            log.warning(f"Skipping creating Role {iam_role_name}: Already exists")

    def delete_role(self, name):
        """Delete the given IAM role and all inline policies"""
        try:
            role = self.boto3_session.resource("iam").Role(name)
            role.load()
        except botocore.exceptions.ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchEntity":
                log.warning(f"Skipping delete of Role {name}: Does not exist")
                return
            raise e

        for policy in role.attached_policies.all():
            role.detach_policy(PolicyArn=policy.arn)

        for policy in role.policies.all():
            policy.delete()

        role.delete()

    def attach_policy(self, iam_role_name, attach_policies):

        try:
            role = self.boto3_session.resource("iam").Role(iam_role_name)
            role.load()
        except botocore.exceptions.ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchEntity":
                log.warning(f"Role {iam_role_name}: Does not exist")
                raise e

        for attach_policy in attach_policies or []:
            role.attach_policy(
                PolicyArn=iam_arn(f"policy/{attach_policy}"),
            )

    def remove_policy(self, iam_role_name, remove_policies):

        try:
            role = self.boto3_session.resource("iam").Role(iam_role_name)
            role.load()
        except botocore.exceptions.ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchEntity":
                log.warning(f"Role {iam_role_name}: Does not exist")
                raise e

        for policy in remove_policies or []:
            try:
                role.detach_policy(PolicyArn=iam_arn(f"policy/{policy}"))
            except botocore.exceptions.ClientError as e:
                if e.response["Error"]["Code"] == "NoSuchEntity":
                    log.warning(f"Policy {policy}: Not attached, skipping")
                    continue
                raise e

    def list_role_names(self, prefix="/"):
        roles = self.boto3_session.resource("iam").roles.filter(PathPrefix=prefix).all()
        return [role.name for role in list(roles)]

    def grant_bucket_access(self, role_name, bucket_arn, access_level, path_arns=None):
        path_arns = path_arns or []
        if access_level not in ("readonly", "readwrite"):
            raise ValueError("access_level must be one of 'readwrite' or 'readonly'")

        if bucket_arn and not path_arns:
            path_arns = [bucket_arn]

        role = self.boto3_session.resource("iam").Role(role_name)
        policy = S3AccessPolicy(role.Policy("s3-access"))
        policy.revoke_access(bucket_arn)
        policy.grant_list_access(bucket_arn)
        for arn in path_arns:
            policy.grant_object_access(arn, access_level)
        policy.put()

    def grant_folder_access(self, role_name, root_folder_path, access_level, paths):

        if access_level not in ("readonly", "readwrite"):
            raise ValueError("access_level must be one of 'readwrite' or 'readonly'")

        role = self.boto3_session.resource("iam").Role(role_name)
        policy = S3AccessPolicy(role.Policy("s3-access"))
        policy.revoke_folder_access(root_folder_path=root_folder_path)
        policy.grant_folder_access(
            root_folder_path=root_folder_path,
            access_level=access_level,
            paths=paths,
        )
        policy.put()

    def revoke_bucket_access(self, role_name, bucket_arn=None):
        if not bucket_arn:
            log.warning(f"Asked to revoke {role_name} role access to nothing")
            return

        try:
            role = self.boto3_session.resource("iam").Role(role_name)
            role.load()
        except botocore.exceptions.ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchEntity":
                log.warning(f"Role '{role_name}' doesn't exist: Nothing to revoke")
                return
            raise e

        policy = S3AccessPolicy(role.Policy("s3-access"))
        policy.revoke_access(bucket_arn)
        policy.put()

    def revoke_folder_access(self, role_name, root_folder_path):
        try:
            role = self.boto3_session.resource("iam").Role(role_name)
            role.load()
        except botocore.exceptions.ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchEntity":
                log.warning(f"Role '{role_name}' doesn't exist: Nothing to revoke")
                return
            raise e

        policy = S3AccessPolicy(role.Policy("s3-access"))
        policy.revoke_folder_access(root_folder_path=root_folder_path)
        policy.put()

    def list_attached_policies(self, role_name):
        try:
            role = self.boto3_session.resource("iam").Role(role_name)
            return list(role.attached_policies.all())
        except botocore.exceptions.ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchEntity":
                log.warning(f"Role '{role_name}' doesn't exist")
                return []
            raise e


class AWSFolder(AWSService):
    @staticmethod
    def _ensure_trailing_slash(folder_name):
        if not folder_name.endswith("/"):
            folder_name = f"{folder_name}/"
        return folder_name

    def create(self, datasource_name, *args):
        folder_name = datasource_name.split("/")[-1]
        folder_name = self._ensure_trailing_slash(folder_name)
        s3 = self.boto3_session.resource("s3")
        s3.Object(bucket_name=settings.S3_FOLDER_BUCKET_NAME, key=folder_name).put()

    def exists(self, folder_name):
        s3_client = self.boto3_session.client("s3")
        bucket_name, folder_name = folder_name.split("/")
        folder_name = self._ensure_trailing_slash(folder_name)
        try:
            s3_client.get_object(Bucket=bucket_name, Key=folder_name)
            return True
        except botocore.exceptions.ClientError:
            return False

    def get_objects(self, bucket_name, folder_name):
        bucket = self.boto3_session.resource("s3").Bucket(bucket_name)
        return bucket.objects.filter(Prefix=f"{folder_name}/")

    def archive_object(self, key, source_bucket_name=None, delete_original=True):
        source_bucket_name = source_bucket_name or settings.S3_FOLDER_BUCKET_NAME
        copy_source = {"Bucket": source_bucket_name, "Key": key}
        archive_bucket = self.boto3_session.resource("s3").Bucket(settings.S3_ARCHIVE_BUCKET_NAME)
        new_key = f"{archive_bucket.name}/{key}"

        archive_bucket.copy(copy_source, new_key)
        log.info(f"Moved {key} to {new_key}")
        if delete_original:
            self.boto3_session.resource("s3").Object(source_bucket_name, key).delete()
            log.info(f"deleted original: {source_bucket_name}/{key}")


class AWSBucket(AWSService):
    def create(self, bucket_name, is_data_warehouse=False):
        s3_resource = self.boto3_session.resource("s3")
        s3_client = self.boto3_session.client("s3")
        try:
            bucket = s3_resource.create_bucket(
                Bucket=bucket_name,
                ACL="private",
                CreateBucketConfiguration={
                    "LocationConstraint": settings.BUCKET_REGION,
                },
            )
            # Enable versioning by default.
            # https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3.html?highlight=s3#S3.BucketVersioning  # noqa: E501
            versioning = bucket.Versioning()
            versioning.enable()
            # Set bucket lifecycle. Send non-current versions of files to glacier
            # storage after 30 days.
            # https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3.html#S3.Client.put_bucket_lifecycle_configuration  # noqa: E501
            lifecycle_id = f"{bucket_name}_lifecycle_configuration"
            s3_client.put_bucket_lifecycle_configuration(
                Bucket=bucket_name,
                LifecycleConfiguration={
                    "Rules": [
                        {
                            "ID": lifecycle_id,
                            "Status": "Enabled",
                            "Prefix": "",
                            "NoncurrentVersionTransitions": [
                                {
                                    "NoncurrentDays": 30,
                                    "StorageClass": "GLACIER",
                                },
                            ],
                        },
                    ]
                },
            )
            if is_data_warehouse:
                self._tag_bucket(bucket, {"buckettype": "datawarehouse"})

        except s3_resource.meta.client.exceptions.BucketAlreadyOwnedByYou:
            log.warning(f"Skipping creating Bucket {bucket_name}: Already exists")
            return

        bucket.Logging().put(
            BucketLoggingStatus={
                "LoggingEnabled": {
                    "TargetBucket": settings.LOGS_BUCKET_NAME,
                    "TargetPrefix": f"{bucket_name}/",
                }
            }
        )
        bucket.meta.client.put_bucket_encryption(
            Bucket=bucket_name,
            ServerSideEncryptionConfiguration={
                "Rules": [
                    {
                        "ApplyServerSideEncryptionByDefault": {
                            "SSEAlgorithm": "AES256",
                        },
                    }
                ]
            },
        )
        bucket.meta.client.put_public_access_block(
            Bucket=bucket_name,
            PublicAccessBlockConfiguration={
                "BlockPublicAcls": True,
                "IgnorePublicAcls": True,
                "BlockPublicPolicy": True,
                "RestrictPublicBuckets": True,
            },
        )

        self._apply_tls_restrictions(s3_client, bucket_name)
        return bucket

    def _apply_tls_restrictions(self, client, bucket_name):
        """it assumes that this is a new bucket with no policies & creates it"""
        tls_statement = deepcopy(BUCKET_TLS_STATEMENT)
        arns: list(str) = [arn.format(bucket_arn=bucket_name) for arn in tls_statement["Resource"]]
        tls_statement["Resource"] = arns
        bucket_policy = dict(Version="2012-10-17", Statement=[tls_statement])
        client.put_bucket_policy(Bucket=bucket_name, Policy=json.dumps(bucket_policy))

    def _tag_bucket(self, boto_bucket, tags):
        """
        Tags the bucket with the given tags

        - `boto_bucket` is boto resource
        - `tags` is a dictionary

        NOTE: The tags provided are merged with existing tags (if any)

        example:

        existing tags : {"buckettype": "datawarehouse"}
        new tags: {"to-archive": "true"}
        result: {"buckettype": "datawarehouse", "to-archive": "true"}

        example:

        existing tags : {"colour": "red", "foo": "bar"}
        new tags: {"colour": "BLUE", "buckettype": "datawarehouse"}
        result: {"colour": "BLUE", "foo": "bar", "buckettype": "datawarehouse"}
        """

        tagging = boto_bucket.Tagging()

        # Get existing tag set
        existing_tag_set = []
        try:
            existing_tag_set = tagging.tag_set
        except botocore.exceptions.ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchTagSet":
                existing_tag_set = []
            else:
                raise e

        # merge existing tags with new ones - new have precedence
        tags_existing = {tag["Key"]: tag["Value"] for tag in existing_tag_set}
        tags_new = {**tags_existing, **tags}

        # convert dictionary to boto/TagSet list/format
        tag_set = [{"Key": k, "Value": v} for k, v in tags_new.items()]

        # Update tags
        tagging.put(Tagging={"TagSet": tag_set})

    def tag_bucket(self, bucket_name, tags):
        """Add the given `tags` to the S3 bucket called `bucket_name`"""
        s3_resource = self.boto3_session.resource("s3")
        try:
            bucket = s3_resource.Bucket(bucket_name)
            self._tag_bucket(bucket, tags)
        except s3_resource.meta.client.exceptions.NoSuchBucket:
            log.warning(f"Bucket {bucket_name} doesn't exist")

    def exists(self, bucket_name):
        try:
            s3_client = self.boto3_session.client("s3")
            s3_client.head_bucket(Bucket=bucket_name)
            return True
        except botocore.exceptions.ClientError:
            return False


class AWSPolicy(AWSService):
    def create_policy(self, name, path, policy_document=None):
        policy_document = policy_document or BASE_S3_ACCESS_POLICY
        iam = self.boto3_session.resource("iam")
        try:
            iam.create_policy(
                PolicyName=name,
                Path=path,
                PolicyDocument=json.dumps(policy_document),
            )
        except iam.meta.client.exceptions.EntityAlreadyExistsException:
            log.warning(f"Skipping creating policy {path}{name}: Already exists")

    def update_policy_members(self, policy_arn, role_names):
        policy = self.boto3_session.resource("iam").Policy(policy_arn)
        members = set(policy.attached_roles.all())
        existing = {member.role_name for member in members}

        for role in role_names - existing:
            policy.attach_role(RoleName=role)

        for role in existing - role_names:
            policy.detach_role(RoleName=role)

    def delete_policy(self, policy_arn):
        policy = self.boto3_session.resource("iam").Policy(policy_arn)
        try:
            policy.load()
        except policy.meta.client.exceptions.NoSuchEntityException:
            log.warning(f"Skipping deletion of policy {policy_arn}: Does not exist")
            return

        for role in policy.attached_roles.all():
            policy.detach_role(RoleName=role.name)

        for version in policy.versions.all():
            if version.version_id != policy.default_version_id:
                version.delete()

        policy.delete()

    def grant_folder_access(self, policy_arn, root_folder_path, access_level, paths=None):

        if access_level not in ("readonly", "readwrite"):
            raise ValueError("access_level must be one of 'readwrite' or 'readonly'")

        policy = self.boto3_session.resource("iam").Policy(policy_arn)
        policy = ManagedS3AccessPolicy(policy)
        policy.revoke_folder_access(root_folder_path=root_folder_path)
        policy.grant_folder_access(
            root_folder_path=root_folder_path,
            access_level=access_level,
            paths=paths,
        )
        policy.put()

    def grant_policy_bucket_access(self, policy_arn, bucket_arn, access_level, path_arns=None):
        if access_level not in ("readonly", "readwrite"):
            raise ValueError("access_level must be 'readonly' or 'readwrite'")

        if bucket_arn and not path_arns:
            path_arns = [bucket_arn]

        policy = self.boto3_session.resource("iam").Policy(policy_arn)
        policy = ManagedS3AccessPolicy(policy)
        policy.revoke_access(bucket_arn)
        policy.grant_list_access(bucket_arn)
        for arn in path_arns or []:
            policy.grant_object_access(arn, access_level)
        policy.put()

    def revoke_policy_bucket_access(self, policy_arn, bucket_arn=None):
        if not bucket_arn:
            log.warning(f"Asked to revoke {policy_arn} group access to nothing")
            return

        policy = self.boto3_session.resource("iam").Policy(policy_arn)
        policy = ManagedS3AccessPolicy(policy)
        policy.revoke_access(bucket_arn)
        policy.put()

    def revoke_policy_folder_access(self, policy_arn, root_folder_path):
        policy = self.boto3_session.resource("iam").Policy(policy_arn)
        policy = ManagedS3AccessPolicy(policy)
        policy.revoke_folder_access(root_folder_path=root_folder_path)
        policy.put()


class AWSParameterStore(AWSService):
    TYPE_SECURE_STRING = "SecureString"

    def __init__(self, assume_role_name=None, profile_name=None):
        super(AWSParameterStore, self).__init__(
            assume_role_name=assume_role_name, profile_name=profile_name
        )
        self.client = self.boto3_session.client("ssm", region_name=settings.AWS_DEFAULT_REGION)

    def create_parameter(self, name, value, role_name, description=""):
        try:
            self.client.put_parameter(
                Name=name,
                Value=value,
                Description=description,
                Type=self.TYPE_SECURE_STRING,
                Tags=[{"Key": "role", "Value": role_name}],
            )
        except self.client.exceptions.ParameterAlreadyExists:
            # TODO do parameter names need to be unique across the platform?
            log.warning(f"Skipping creating Parameter {name} for {role_name}: Already exists")

    def delete_parameter(self, name):
        try:
            self.client.delete_parameter(Name=name)
        except self.client.exceptions.ParameterNotFound:
            log.warning(f"Skipping deleting Parameter {name}: Does not exist")

    def get_parameter(self, name):
        try:
            return self.client.get_parameter(Name=name, WithDecryption=True)
        except self.client.exceptions.ParameterNotFound:
            log.warning(f"Parameter {name}: Does not exist")
            return {}


class AWSSecretManagerError(Exception):
    pass


class AWSSecretManager(AWSService):
    def __init__(self, assume_role_name=None, profile_name=None):
        super(AWSSecretManager, self).__init__(
            assume_role_name=assume_role_name, profile_name=profile_name
        )
        self.client = self.boto3_session.client("secretsmanager")

    def _format_error_message(self, client_error_response):
        return format(
            "{}: {}.".format(
                client_error_response.get("Error"), client_error_response.get("Message")
            )
        )

    def has_existed(self, secret_name: str):
        try:
            self.client.get_secret_value(SecretId=secret_name)
            return True
        except botocore.exceptions.ClientError as error:
            if error.response["Error"]["Code"] == "ResourceNotFoundException":
                return False
            else:
                raise AWSSecretManagerError(self._format_error_message(error.response))

    def create_secret(self, secret_name: str, secret_data):
        try:
            kwargs = {"Name": secret_name}
            if isinstance(secret_data, dict):
                kwargs["SecretString"] = json.dumps(secret_data)
            elif isinstance(secret_data, bytes):
                kwargs["SecretBinary"] = base64.b64encode(secret_data)
            return self.client.create_secret(**kwargs)
        except botocore.exceptions.ClientError as error:
            raise AWSSecretManagerError(self._format_error_message(error.response))

    def get_secret(self, secret_name):
        try:
            response = self.client.get_secret_value(SecretId=secret_name)
            if "SecretString" in response:
                secret_data = json.loads(response["SecretString"])
            else:
                secret_data = base64.b64decode(response["SecretBinary"])
            return secret_data
        except botocore.exceptions.ClientError as error:
            raise AWSSecretManagerError(self._format_error_message(error.response))

    def update_secret(self, secret_name, secret_data):
        try:
            kwargs = {"SecretId": secret_name}
            response = self.client.get_secret_value(SecretId=secret_name)
            if isinstance(secret_data, bytes):
                kwargs["SecretBinary"] = base64.b64encode(secret_data)
            else:
                origin_data = {}
                if "SecretString" in response:
                    origin_data = json.loads(response["SecretString"])
                for key, value in secret_data.items():
                    origin_data[key] = value
                kwargs["SecretString"] = json.dumps(origin_data)
            self.client.update_secret(**kwargs)
        except botocore.exceptions.ClientError as error:
            if error.response["Error"]["Code"] == "ResourceNotFoundException":
                return False
            else:
                raise AWSSecretManagerError(self._format_error_message(error.response))

    def delete_keys_in_secret(self, secret_name, keys_to_delete):
        """
        Deletes keys for a stored entry.
        Same as update_secret, but removes entries accordingly.
        """
        try:
            kwargs = {"SecretId": secret_name}
            response = self.client.get_secret_value(SecretId=secret_name)
            if "SecretString" in response:
                # only update json SecretString, ignore everything else
                origin_data = json.loads(response["SecretString"])
                for key in keys_to_delete:
                    if key in origin_data:
                        del origin_data[key]

                kwargs["SecretString"] = json.dumps(origin_data)
                self.client.update_secret(**kwargs)
                return True
            return False
        except botocore.exceptions.ClientError as error:
            if error.response["Error"]["Code"] == "ResourceNotFoundException":
                return False
            else:
                raise AWSSecretManagerError(self._format_error_message(error.response))

    def delete_secret(self, secret_name, without_recovery=True):
        """
        Choosing True as default value of without_recovery to allow us to create
        secret again in a short period of time, otherwise we have to wait the
        recovery window ends, but it does mean we lose the ability of recovering
        the deletion within recovery window.
        """
        if not self.has_existed(secret_name):
            return

        try:
            response = self.client.delete_secret(
                SecretId=secret_name, ForceDeleteWithoutRecovery=without_recovery
            )
            return response
        except botocore.exceptions.ClientError as error:
            raise AWSSecretManagerError(self._format_error_message(error.response))

    def create_or_update(self, secret_name, secret_data):
        if not self.has_existed(secret_name):
            return self.create_secret(secret_name, secret_data=secret_data)
        else:
            return self.update_secret(secret_name, secret_data=secret_data)

    def get_secret_if_found(self, secret_name: str) -> Optional[dict]:
        if self.has_existed(secret_name):
            return self.get_secret(secret_name)
        return {}


class AWSSQS(AWSService):

    def __init__(self, assume_role_name=None, profile_name=None):
        super(AWSSQS, self).__init__(
            assume_role_name=assume_role_name,
            profile_name=profile_name,
            region_name=settings.SQS_REGION,
        )
        self.client = self.boto3_session.resource("sqs")

    def get_queue(self, name):
        """
        Gets an SQS queue by name.

        :param name: The name that was used to create the queue.
        :return: A Queue object.
        """
        try:
            queue = self.client.get_queue_by_name(QueueName=name)
            log.info("Got queue '%s' with URL=%s", name, queue.url)
        except botocore.exceptions.ClientError as error:
            log.exception("Couldn't get queue named %s.", name)
            raise error
        else:
            return queue

    def send_message(self, queue_name, message_body, message_attributes=None):
        """
        Send a message to an Amazon SQS queue.

        :param queue_name: The queue that receives the message.
        :param message_body: The body text of the message.
        :param message_attributes: Custom attributes of the message. These are key-value
                                   pairs that can be whatever you want.
        :return: The response from SQS that contains the assigned message ID.
        """
        if not message_attributes:
            message_attributes = {}

        queue = self.get_queue(name=queue_name)
        try:
            response = queue.send_message(
                MessageBody=message_body, MessageAttributes=message_attributes
            )
        except botocore.exceptions.ClientError as error:
            log.exception("Send message failed: %s", message_body)
            raise error
        else:
            return response

    def receive_messages(self, queue_name, max_number, wait_time):
        """
        Receive a batch of messages in a single request from an SQS queue.

        :param queue_name: The queue from which to receive messages.
        :param max_number: The maximum number of messages to receive. The actual number
                           of messages received might be less.
        :param wait_time: The maximum time to wait (in seconds) before returning. When
                          this number is greater than zero, long polling is used. This
                          can result in reduced costs and fewer false empty responses.
        :return: The list of Message objects received. These each contain the body
                 of the message and metadata and custom attributes.
        """
        queue = self.get_queue(name=queue_name)
        try:
            messages = queue.receive_messages(
                MessageAttributeNames=["All"],
                MaxNumberOfMessages=max_number,
                WaitTimeSeconds=wait_time,
            )
            for msg in messages:
                log.info("Received message: %s: %s", msg.message_id, msg.body)
        except botocore.exceptions.ClientError as error:
            log.exception("Couldn't receive messages from queue: %s", queue_name)
            raise error
        else:
            return messages

    def delete_messages(self, queue, messages):
        """
        Delete a batch of messages from a queue in a single request.

        :param queue: The queue from which to delete the messages.
        :param messages: The list of messages to delete.
        :return: The response from SQS that contains the list of successful and failed
                 message deletions.
        """
        try:
            entries = [
                {"Id": str(ind), "ReceiptHandle": msg.receipt_handle}
                for ind, msg in enumerate(messages)
            ]
            response = queue.delete_messages(Entries=entries)
            if "Successful" in response:
                for msg_meta in response["Successful"]:
                    log.info("Deleted %s", messages[int(msg_meta["Id"])].receipt_handle)
            if "Failed" in response:
                for msg_meta in response["Failed"]:
                    log.warning("Could not delete %s", messages[int(msg_meta["Id"])].receipt_handle)
        except botocore.exceptions.ClientError:
            log.exception("Couldn't delete messages from queue %s", queue)
        else:
            return response


class AWSQuicksight(AWSService):

    service_name = "quicksight"

    def __init__(self, assume_role_name=None, profile_name=None, region_name=None):
        super().__init__(assume_role_name, profile_name, region_name or "eu-west-1")
        log.info(
            f"Init QuicksightService with assume_role_name: {assume_role_name}, profile_name: {profile_name}, region_name: {region_name}"  # noqa
        )
        self.client = self.boto3_session.client("quicksight")

    def get_embed_url(self, user):

        if not user.justice_email:
            return None

        user_arn = arn(
            service=self.service_name,
            resource=f"user/default/{user.justice_email}",
            region=settings.QUICKSIGHT_ACCOUNT_REGION,
            account=settings.QUICKSIGHT_ACCOUNT_ID,
        )

        response = self.client.generate_embed_url_for_registered_user(
            AwsAccountId=settings.QUICKSIGHT_ACCOUNT_ID,
            UserArn=user_arn,
            ExperienceConfiguration={
                "QuickSightConsole": {
                    "InitialPath": "/start",
                    "FeatureConfigurations": {"StatePersistence": {"Enabled": True}},
                },
            },
            AllowedDomains=settings.QUICKSIGHT_DOMAINS,
        )
        if response:
            return response["EmbedUrl"]

        return response


class AWSLakeFormation(AWSService):

    def __init__(self, assume_role_name=None, profile_name=None, region_name=None):
        super().__init__(assume_role_name, profile_name, region_name)
        self.client = self.boto3_session.client("lakeformation")

    def grant_permissions(self, resource, principal_arn, permissions):
        permissions = permissions
        try:
            response = self.client.grant_permissions(
                CatalogId=settings.AWS_DATA_ACCOUNT_ID,
                Permissions=permissions,
                Principal={"DataLakePrincipalIdentifier": principal_arn},
                Resource=resource,
            )
        except botocore.exceptions.ClientError as error:
            log.exception(error.response["Error"]["Message"])
            raise error

        return response

    def grant_table_permission(
        self, database_name, table_name, principal_arn, permissions, catalog_id=None
    ):
        catalog_id = catalog_id or settings.AWS_DATA_ACCOUNT_ID
        resource = {
            "Table": {
                "CatalogId": catalog_id,
                "DatabaseName": database_name,
                "Name": table_name,
            },
        }
        return self.grant_permissions(
            resource=resource,
            principal_arn=principal_arn,
            permissions=permissions,
        )

    def revoke_permissions(self, resource, principal_arn, permissions):
        permissions = permissions
        try:
            response = self.client.revoke_permissions(
                CatalogId=settings.AWS_DATA_ACCOUNT_ID,
                Permissions=permissions,
                Principal={"DataLakePrincipalIdentifier": principal_arn},
                Resource=resource,
            )
        except botocore.exceptions.ClientError as error:
            log.exception(error.response["Error"]["Message"])
            raise error

        return response

    def revoke_table_permission(
        self, database_name, table_name, principal_arn, permissions, catalog_id=None
    ):
        catalog_id = catalog_id or settings.AWS_DATA_ACCOUNT_ID
        resource = {
            "Table": {
                "CatalogId": catalog_id,
                "DatabaseName": database_name,
                "Name": table_name,
            },
        }
        return self.revoke_permissions(
            resource=resource,
            principal_arn=principal_arn,
            permissions=permissions,
        )

    def list_permissions(self, database_name, table_name, principal_arn=None, catalog_id=None):
        catalog_id = catalog_id or settings.AWS_DATA_ACCOUNT_ID
        resource = {
            "Table": {
                "CatalogId": catalog_id,
                "DatabaseName": database_name,
                "Name": table_name,
            },
        }

        if principal_arn:
            return self.client.list_permissions(
                Resource=resource,
                Principal={"DataLakePrincipalIdentifier": principal_arn},
            )

        return self.client.list_permissions(Resource=resource)

    def create_lf_opt_in(self, database_name, table_name, principal_arn, catalog_id=None):
        catalog_id = catalog_id or settings.AWS_DATA_ACCOUNT_ID

        database_resource = {
            "Database": {
                "CatalogId": catalog_id,
                "Name": database_name,
            },
        }

        table_resource = {
            "Table": {
                "CatalogId": catalog_id,
                "DatabaseName": database_name,
                "Name": table_name,
            },
        }

        opt_ins = self.list_lf_opt_ins(database_name, principal_arn, catalog_id)

        if opt_ins["database"] is None:
            self.client.create_lake_formation_opt_in(
                Resource=database_resource,
                Principal={"DataLakePrincipalIdentifier": principal_arn},
            )

        self.client.create_lake_formation_opt_in(
            Resource=table_resource,
            Principal={"DataLakePrincipalIdentifier": principal_arn},
        )

    def delete_lf_opt_in(self, database_name, table_name, principal_arn, catalog_id=None):
        catalog_id = catalog_id or settings.AWS_DATA_ACCOUNT_ID
        database_resource = {
            "Database": {
                "CatalogId": catalog_id,
                "Name": database_name,
            },
        }

        table_resource = {
            "Table": {
                "CatalogId": catalog_id,
                "DatabaseName": database_name,
                "Name": table_name,
            },
        }

        opt_ins = self.list_lf_opt_ins(database_name, principal_arn, catalog_id)

        if len(opt_ins["tables"]) == 1:
            self.client.delete_lake_formation_opt_in(
                Resource=database_resource,
                Principal={"DataLakePrincipalIdentifier": principal_arn},
            )

        self.client.delete_lake_formation_opt_in(
            Resource=table_resource,
            Principal={"DataLakePrincipalIdentifier": principal_arn},
        )

    def list_lf_opt_ins(self, database_name, principal_arn, catalog_id=None):
        catalog_id = catalog_id or settings.AWS_DATA_ACCOUNT_ID
        result = {
            "database": None,
            "tables": [],
        }

        response = self.client.list_lake_formation_opt_ins(
            Principal={"DataLakePrincipalIdentifier": principal_arn}
        )["LakeFormationOptInsInfoList"]

        for resource_object in response:
            resource = resource_object["Resource"]
            if "Database" in resource and resource["Database"]["Name"] == database_name:
                result["database"] = resource
            elif "Table" in resource:
                if resource["Table"]["DatabaseName"] == database_name:
                    result["tables"].append(resource)

        return result


class AWSGlue(AWSService):

    def __init__(self, assume_role_name=None, profile_name=None, region_name=None):
        super().__init__(assume_role_name, profile_name, region_name)
        self.client = self.boto3_session.client("glue")

    def get_databases(self, catalog_id=None):
        try:
            response = self.client.get_databases(
                CatalogId=catalog_id or settings.AWS_DATA_ACCOUNT_ID
            )
        except botocore.exceptions.ClientError as error:
            log.exception(error.response["Error"]["Message"])
            raise error

        return response

    def get_database(self, database_name, catalog_id=None):
        try:
            response = self.client.get_database(
                CatalogId=catalog_id or settings.AWS_DATA_ACCOUNT_ID, Name=database_name
            )
        except botocore.exceptions.ClientError as error:
            log.exception(error.response["Error"]["Message"])
            raise error

        return response

    def get_tables(self, database_name, catalog_id=None):
        try:
            response = self.client.get_tables(
                CatalogId=catalog_id or settings.AWS_DATA_ACCOUNT_ID, DatabaseName=database_name
            )
        except botocore.exceptions.ClientError as error:
            log.exception(error.response["Error"]["Message"])
            raise error

        return response

    def get_table(self, database_name, table_name, catalog_id=None):
        try:
            response = self.client.get_table(
                CatalogId=catalog_id or settings.AWS_DATA_ACCOUNT_ID,
                DatabaseName=database_name,
                Name=table_name,
            )
        except botocore.exceptions.ClientError as error:
            log.exception(error.response["Error"]["Message"])
            raise error

        return response
