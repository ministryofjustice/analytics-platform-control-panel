# Standard library
import os
import secrets
from copy import deepcopy
from enum import Enum

# Third-party
import requests
import structlog
from django.conf import settings
from django.core.exceptions import MultipleObjectsReturned, ObjectDoesNotExist

# First-party/Local
from controlpanel.api import auth0, helm
from controlpanel.api.aws import (
    AWSBucket,
    AWSFolder,
    AWSParameterStore,
    AWSPolicy,
    AWSRole,
    iam_arn,
    s3_arn,
)
from controlpanel.api.github import GithubAPI, extract_repo_info_from_url
from controlpanel.api.kubernetes import KubernetesClient

log = structlog.getLogger(__name__)


TOOL_DEPLOYING = "Deploying"
TOOL_DEPLOY_FAILED = "Failed"
TOOL_IDLED = "Idled"
TOOL_NOT_DEPLOYED = "Not deployed"
TOOL_READY = "Ready"
TOOL_RESTARTING = "Restarting"
TOOL_STATUS_UNKNOWN = "Unknown"
HOME_RESETTING = "Resetting"
HOME_RESET_FAILED = "Failed"
HOME_RESET = "Reset"


BASE_ASSUME_ROLE_POLICY = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {
                "Service": "ec2.amazonaws.com",
            },
            "Action": "sts:AssumeRole",
        }
    ],
}


class AWSRoleCategory(str, Enum):
    app = "APP"
    user = "USER"


class HomeDirectoryResetError(Exception):
    """
    Raised if a home directory cannot be reset.
    """

    pass


class AWSServiceCredentialSettings:
    """This class is responsible for defining the mapping between coding object
    (class[.func] or function) for creating AWS resource or using AWS service
    for achieving something. The setting may be imported through external source
    e.g. config yaml file or db in the future, such process will be outside this
    class for now, only the json object will be pass in. The assumed json
    structure is 2 level dictionary as below:
    AWS_ROLES_MAP:
        DEFAULT: <The name of the environment variable which contains the actual name of the aws-assumed-role> # noqa : E501
        <Entity category>
            DEFAULT: <The name of the environment variable which contains the actual name of the aws-assumed-role> # noqa : E501
            <AWS service name>: <The name of the environment variable which contains the actual name of the aws-assumed-role> # noqa : E501
    Entity category: by default, it will be same as the entity class name, but each entity class can define their own # noqa : E501
    DEFAULT: is the default role which will be used if an lower level config couldn't be found # noqa : E501
    AWS service name: by default, it will be same as the class name of AWS service but aws service can define their own # noqa : E501
    one example would be
    AWS_ROLES_MAP:
      DEFAULT_ROLE: AWS_DATA_ACCOUNT_ROLE
      USER:
        DEFAULT: AWS_DATA_ACCOUNT_ROLE
        AWSROLE: AWS_DATA_ACCOUNT_ROLE
      APP:
        DEFAULT: AWS_DATA_ACCOUNT_ROLE
    """

    _DEFAULT_SETTING_ROLE_KEY_ = "DEFAULT"

    def __init__(self, aws_rols_map=None):
        self.mapping = aws_rols_map

    def _locate_setting(self, setting_key):
        """
        Check a few places, the priorities are below (highest first)
        - environment variable
        - settings
        - None
        """
        if os.getenv(setting_key):
            return os.getenv(setting_key)
        if hasattr(settings, setting_key):
            return getattr(settings, setting_key)
        return None

    def get_credential_setting(self, category_name, aws_service_name):
        category_name = category_name or self._DEFAULT_SETTING_ROLE_KEY_
        found_role_name = self.mapping.get(category_name.upper(), {}).get(
            aws_service_name.upper(), None
        )
        if not found_role_name:
            found_role_name = self.mapping.get(category_name.upper(), {}).get(
                self._DEFAULT_SETTING_ROLE_KEY_
            )

        if not found_role_name:
            found_role_name = self.mapping.get(self._DEFAULT_SETTING_ROLE_KEY_)
        return self._locate_setting(found_role_name)


class EntityResource:

    ENTITY_ASSUME_ROLE_CATEGORY = None

    def __init__(self):
        self.aws_credential_settings = AWSServiceCredentialSettings(
            settings.AWS_ROLES_MAP
        )
        self._init_aws_services()

    def _init_aws_services(self):
        pass

    @property
    def entity_category_key(self):
        return self.ENTITY_ASSUME_ROLE_CATEGORY or (self.__class__.__name__).upper()

    def get_aws_service_name(self, aws_service_class):
        try:
            aws_service_name = aws_service_class.ASSUME_ROLE_NAME
        except Exception:
            aws_service_name = aws_service_class.__name__
        return aws_service_name

    def get_assume_role(
        self, aws_service_class, aws_role_category=None, aws_service_name=None
    ):
        aws_role_category = aws_role_category or self.entity_category_key
        aws_service_name = aws_service_name or self.get_aws_service_name(
            aws_service_class
        )
        assume_role_name = self.aws_credential_settings.get_credential_setting(
            category_name=aws_role_category, aws_service_name=aws_service_name
        )
        return assume_role_name

    def create_aws_service(
        self, aws_service_class, aws_role_category=None, aws_service_name=None
    ):
        return aws_service_class(
            assume_role_name=self.get_assume_role(
                aws_service_class=aws_service_class,
                aws_role_category=aws_role_category,
                aws_service_name=aws_service_name,
            )
        )


class User(EntityResource):
    """
    Wraps User model to provide convenience methods to access K8S and AWS

    A user is represented by an IAM role, which is assumed by their tools.
    """

    OIDC_STATEMENT = {
        "Effect": "Allow",
        "Principal": {
            "Federated": iam_arn(f"oidc-provider/{settings.OIDC_DOMAIN}/"),
        },
        "Action": "sts:AssumeRoleWithWebIdentity",
    }

    EKS_STATEMENT = {
        "Effect": "Allow",
        "Principal": {
            "Federated": iam_arn(f"oidc-provider/{settings.OIDC_EKS_PROVIDER}"),
        },
        "Action": "sts:AssumeRoleWithWebIdentity",
        "Condition": {"StringLike": {}},
    }

    READ_INLINE_POLICIES = f"{settings.ENV}-read-user-roles-inline-policies"

    ATTACH_POLICIES = [
        READ_INLINE_POLICIES,
        "airflow-dev-ui-access",
        "airflow-prod-ui-access",
    ]

    def __init__(self, user):
        self.user = user
        self.k8s_namespace = f"user-{self.user.slug}"
        self.eks_cpanel_namespace = "cpanel"
        super(User, self).__init__()

    def _init_aws_services(self):
        self.aws_role_service = self.create_aws_service(AWSRole)

    @property
    def user_helm_charts(self):
        # The full list of the charts required for a user under different situations
        # TODO this helm charts should be stored somewhere rather than hard coding here
        # The order defined in the follow list is important
        return {
            "installation": [
                {
                    "namespace": self.eks_cpanel_namespace,
                    "release": f"bootstrap-user-{self.user.slug}",
                    "chart": f"{settings.HELM_REPO}/bootstrap-user",
                    "values": {"Username": self.user.slug},
                },
                {
                    "namespace": self.k8s_namespace,
                    "release": f"provision-user-{self.user.slug}",
                    "chart": f"{settings.HELM_REPO}/provision-user",
                    "values": {
                        "Username": self.user.slug,
                        "Efsvolume": settings.EFS_VOLUME,
                        "OidcDomain": settings.OIDC_DOMAIN,
                        "Email": self.user.email,
                        "Fullname": self.user.name,
                    },
                },
            ],
            "reset_home": [
                {
                    "namespace": self.k8s_namespace,
                    "release": f"reset-user-efs-home-{self.user.slug}",
                    "chart": f"{settings.HELM_REPO}/reset-user-efs-home",
                    "values": {"Username": self.user.slug},
                }
            ],
        }

    @property
    def iam_role_name(self):
        return f"{settings.ENV}_user_{self.user.username.lower()}"

    def _run_helm_install_command(self, helm_chart_item):
        values = []
        for key, value in helm_chart_item["values"].items():
            values.append("{}={}".format(key, value))
        helm.upgrade_release(
            helm_chart_item["release"],  # release
            helm_chart_item["chart"],  # chart
            f"--namespace={helm_chart_item['namespace']}",
            "--set=" + (",".join(values)),
        )

    def _init_user(self):
        for helm_chart_item in self.user_helm_charts["installation"]:
            self._run_helm_install_command(helm_chart_item)

    @staticmethod
    def aws_user_policy(user_auth0_id, user_name):
        policy = deepcopy(BASE_ASSUME_ROLE_POLICY)
        oidc_statement = deepcopy(User.OIDC_STATEMENT)
        oidc_statement["Condition"] = {
            "StringEquals": {
                f"{settings.OIDC_DOMAIN}/:sub": user_auth0_id,
            }
        }
        policy["Statement"].append(oidc_statement)
        eks_statement = deepcopy(User.EKS_STATEMENT)
        match = f"system:serviceaccount:user-{user_name}:{user_name}-*"
        eks_statement["Condition"]["StringLike"] = {
            f"{settings.OIDC_EKS_PROVIDER}:sub": match
        }
        policy["Statement"].append(eks_statement)
        return policy

    def create(self):
        self.aws_role_service.create_role(
            self.iam_role_name,
            User.aws_user_policy(self.user.auth0_id, self.user.slug),
            User.ATTACH_POLICIES,
        )
        self._init_user()

    def reset_home(self):
        """
        Reset the user's home directory.
        """
        for helm_chart_item in self.user_helm_charts["reset_home"]:
            self._run_helm_install_command(helm_chart_item)

    def _uninstall_helm_charts(self, related_namespace, hel_charts, dry_run=False):
        if not hel_charts:
            return

        helm.delete(related_namespace, *hel_charts, dry_run=dry_run)

    def _filter_out_installation_charts(self, helm_charts):
        init_installed_charts = []
        for helm_chart_item in self.user_helm_charts["installation"]:
            if helm_chart_item["release"] in helm_charts:
                init_installed_charts.append(helm_chart_item["release"])
        # Removed those initially installed charts from the charts which are
        # retrieved from the namespace
        for helm_chart_item in init_installed_charts:
            helm_charts.remove(helm_chart_item)
        return init_installed_charts

    def delete_user_helm_charts(self, dry_run=False):
        user_releases = helm.list_releases(namespace=self.k8s_namespace)
        cpanel_releases = helm.list_releases(
            namespace=self.eks_cpanel_namespace, release=f"user-{self.user.slug}"
        )

        init_installed_charts = self._filter_out_installation_charts(user_releases)
        self._uninstall_helm_charts(self.k8s_namespace, user_releases, dry_run=dry_run)
        self._uninstall_helm_charts(
            self.k8s_namespace, init_installed_charts, dry_run=dry_run
        )

        # Only remove the installed charts from cpanel namespace
        init_installed_charts = self._filter_out_installation_charts(cpanel_releases)
        self._uninstall_helm_charts(
            self.eks_cpanel_namespace, init_installed_charts, dry_run=dry_run
        )

    def delete(self):
        self.aws_role_service.delete_role(self.user.iam_role_name)
        self.delete_user_helm_charts()

    def grant_bucket_access(self, bucket_arn, access_level, path_arns=[]):
        self.aws_role_service.grant_bucket_access(
            self.iam_role_name, bucket_arn, access_level, path_arns
        )

    def grant_folder_access(self, bucket_arn, access_level):
        self.aws_role_service.grant_folder_access(
            self.iam_role_name, bucket_arn, access_level
        )

    def revoke_bucket_access(self, bucket_arn):
        self.aws_role_service.revoke_bucket_access(self.iam_role_name, bucket_arn)

    def has_required_installation_charts(self):
        """Checks if the expected helm charts exist for the user."""
        installed_helm_charts = helm.list_releases(namespace=self.k8s_namespace)
        installed_helm_charts.extend(
            helm.list_releases(
                namespace=self.eks_cpanel_namespace, release=f"user-{self.user.slug}"
            )
        )
        for helm_chart_item in self.user_helm_charts["installation"]:
            if helm_chart_item["release"] not in installed_helm_charts:
                return False
        return True


class App(EntityResource):
    """
    Responsible for the apps-related interactions with the k8s cluster and AWS
    """

    IP_RANGES = "IP_RANGES"
    AUTH0_CLIENT_ID = "AUTH0_CLIENT_ID"
    AUTH0_CLIENT_SECRET = "AUTH0_CLIENT_SECRET"
    AUTH0_DOMAIN = "AUTH0_DOMAIN"
    AUTH0_CONNECTIONS = "AUTH0_CONNECTIONS"
    AUTHENTICATION_REQUIRED = "AUTHENTICATION_REQUIRED"
    AUTH0_PASSWORDLESS = "AUTH0_PASSWORDLESS"

    def __init__(self, app, github_api_token=None, auth0_instance=None):
        super(App, self).__init__()
        self.app = app
        self.github_api_token = github_api_token
        self.auth0_instance = auth0_instance

    def _get_auth0_instance(self):
        if not self.auth0_instance:
            self.auth0_instance = auth0.ExtendedAuth0()
        return self.auth0_instance

    def _init_aws_services(self):
        self.aws_role_service = self.create_aws_service(AWSRole)

    def create_or_update_secrets(self, env_name, secret_data):
        org_name, repo_name = extract_repo_info_from_url(self.app.repo_url)
        GithubAPI(self.github_api_token, github_org=org_name).create_or_update_repo_env_secrets(
            repo_name, env_name, secret_data
        )

    def _create_secrets(self, env_name, client=None):
        secret_data: dict = {
            App.IP_RANGES: self.app.env_allowed_ip_ranges(env_name=env_name)
        }
        if client:
            secret_data[App.AUTH0_CLIENT_ID] = client["client_id"]
            secret_data[App.AUTH0_CLIENT_SECRET] = client["client_secret"]

        self.create_or_update_secrets(env_name=env_name, secret_data=secret_data)

    def _create_env_vars(
        self,
        env_name,
        disable_authentication,
        connections,
        client=None,
    ):
        if client:
            env_data: dict = {
                App.AUTH0_DOMAIN: settings.OIDC_DOMAIN,
                App.AUTH0_PASSWORDLESS: "email" in connections,
                App.AUTHENTICATION_REQUIRED: not disable_authentication,
            }
        else:
            env_data: dict = {App.AUTHENTICATION_REQUIRED: not disable_authentication}

        self._create_envs(env_name=env_name, env_data=env_data)

    def _create_envs(self, env_name, env_data):
        org_name, repo_name = extract_repo_info_from_url(self.app.repo_url)
        GithubAPI(self.github_api_token, github_org=org_name).create_repo_env_vars(
            repo_name, env_name, env_data
        )

    def _is_hidden_secret(self, name):
        for item in settings.OTHER_SYSTEM_SECRETS or []:
            if name.startswith(item) or item in name:
                return True
        return False

    def _add_missing_mandatory_secrets(self, env_name, app_secrets, created_secret_names):
        not_created_ones = list(
            set(settings.AUTH_SETTINGS_SECRETS) - set(created_secret_names)
        )
        for item_name in not_created_ones:
            app_secrets.append(
                {
                    "name": item_name,
                    "env_name": env_name,
                    "value": None,
                    "created": False,
                    "removable": False,
                    "editable": item_name not in settings.AUTH_SETTINGS_NO_EDIT,
                }
            )

    def _add_missing_mandatory_vars(self, env_name, app_env_vars, created_var_names):
        not_created_ones = list(
            set(settings.AUTH_SETTINGS_ENVS) - set(created_var_names)
        )
        for item_name in not_created_ones:
            app_env_vars.append(
                {
                    "name": item_name,
                    "value": None,
                    "env_name": env_name,
                    "created": False,
                    "removable": False,
                    "editable": item_name not in settings.AUTH_SETTINGS_NO_EDIT,
                }
            )

    @property
    def iam_role_name(self):
        return f"{settings.ENV}_app_{self.app.slug}"

    def create_iam_role(self):
        self.aws_role_service.create_role(self.iam_role_name, BASE_ASSUME_ROLE_POLICY)

    def grant_bucket_access(self, bucket_arn, access_level, path_arns):
        self.aws_role_service.grant_bucket_access(
            self.iam_role_name, bucket_arn, access_level, path_arns
        )

    def revoke_bucket_access(self, bucket_arn):
        self.aws_role_service.revoke_bucket_access(self.iam_role_name, bucket_arn)

    def delete(self):
        self.aws_role_service.delete_role(self.iam_role_name)
        if self.github_api_token:
            for env_name in self.get_deployment_envs():
                self.remove_auth_settings(env_name)

    def list_role_names(self):
        return self.aws_role_service.list_role_names()

    @staticmethod
    def format_github_key_name(key_name):
        """
        Format the self-defined secret/variable by adding prefix if
        create/update value back to github and there is no prefix in the name
        """
        if key_name not in settings.AUTH_SETTINGS_ENVS \
                and key_name not in settings.AUTH_SETTINGS_SECRETS:
            if not key_name.startswith(settings.APP_SELF_DEFINE_SETTING_PREFIX):
                return f"{settings.APP_SELF_DEFINE_SETTING_PREFIX}{key_name}"
        return key_name

    @staticmethod
    def get_github_key_display_name(key_name):
        """
        Format the self-defined secret/variable by removing the prefix
        if reading it from github and there is prefix in the name
        """
        if key_name and key_name not in settings.AUTH_SETTINGS_ENVS \
                and key_name not in settings.AUTH_SETTINGS_SECRETS:
            if settings.APP_SELF_DEFINE_SETTING_PREFIX in key_name:
                return key_name.replace(
                    settings.APP_SELF_DEFINE_SETTING_PREFIX, "")
        return key_name

    def create_or_update_secret(self, env_name, secret_key, secret_value):
        org_name, repo_name = extract_repo_info_from_url(self.app.repo_url)
        GithubAPI(self.github_api_token, github_org=org_name).create_or_update_repo_env_secret(
            repo_name,
            env_name,
            secret_key,
            secret_value
        )

    def delete_secret(self, env_name, secret_name):
        org_name, repo_name = extract_repo_info_from_url(self.app.repo_url)
        try:
            GithubAPI(self.github_api_token, github_org=org_name).delete_repo_env_secret(
                repo_name,
                env_name=env_name,
                secret_name=secret_name
            )
        except requests.exceptions.HTTPError as error:
            if error.response.status_code != 404:
                raise Exception(str(error))

    def get_env_var(self, env_name, key_name):
        org_name, repo_name = extract_repo_info_from_url(self.app.repo_url)
        return GithubAPI(self.github_api_token, github_org=org_name).get_repo_env_var(
            repo_name, env_name, key_name
        )

    def create_or_update_env_var(self, env_name, key_name, key_value):
        org_name, repo_name = extract_repo_info_from_url(self.app.repo_url)
        GithubAPI(self.github_api_token, github_org=org_name).create_or_update_env_var(
            repo_name,
            env_name,
            key_name,
            key_value
        )

    def delete_env_var(self, env_name, key_name):
        org_name, repo_name = extract_repo_info_from_url(self.app.repo_url)
        try:
            GithubAPI(self.github_api_token, github_org=org_name).delete_repo_env_var(
                repo_name,
                env_name,
                key_name
            )
        except requests.exceptions.HTTPError as error:
            if error.response.status_code != 404:
                raise Exception(str(error))

    def get_deployment_envs(self):
        org_name, repo_name = extract_repo_info_from_url(self.app.repo_url)
        return GithubAPI(self.github_api_token, github_org=org_name).get_repo_envs(
            repo_name=repo_name
        )

    def get_env_secrets(self, env_name):
        org_name, repo_name = extract_repo_info_from_url(self.app.repo_url)
        app_secrets = []
        created_secret_names = []
        for item in GithubAPI(self.github_api_token, github_org=org_name).get_repo_env_secrets(
            repo_name=repo_name, env_name=env_name
        ):
            if self._is_hidden_secret(item["name"]):
                continue
            value = settings.SECRET_DISPLAY_VALUE
            if item["name"] == App.IP_RANGES:
                value = self.app.env_allowed_ip_ranges_names(env_name=env_name)
            app_secrets.append(
                {
                    "name": item["name"],
                    "env_name": env_name,
                    "value": value,
                    "created": True,
                    "removable": item["name"] not in settings.AUTH_SETTINGS_SECRETS,
                    "editable": item["name"] not in settings.AUTH_SETTINGS_NO_EDIT,
                }
            )
            created_secret_names.append(item["name"])
        self._add_missing_mandatory_secrets(env_name, app_secrets, created_secret_names)
        return app_secrets

    def get_env_vars(self, env_name):
        org_name, repo_name = extract_repo_info_from_url(self.app.repo_url)
        app_env_vars = []
        created_var_names = []
        for item in GithubAPI(self.github_api_token, github_org=org_name).get_repo_env_vars(
            repo_name, env_name=env_name
        ):
            app_env_vars.append(
                {
                    "name": item["name"],
                    "value": item["value"],
                    "created": True,
                    "env_name": env_name,
                    "removable": item["name"] not in settings.AUTH_SETTINGS_ENVS,
                    "editable": item["name"] not in settings.AUTH_SETTINGS_NO_EDIT,
                }
            )
            created_var_names.append(item["name"])
        self._add_missing_mandatory_vars(env_name, app_env_vars, created_var_names)
        return app_env_vars

    def create_auth_settings(
            self, env_name, disable_authentication=False, connections=None, app_domain=None
    ):
        client = None
        group = None
        if not disable_authentication:
            client, group = self._get_auth0_instance().setup_auth0_client(
                client_name=self.app.auth0_client_name(env_name),
                app_url_name=self.app.app_url_name(env_name),
                connections=connections,
                app_domain=app_domain
            )
            self.app.save_auth_settings(
                env_name=env_name, client=client, group=group)
        self._create_secrets(env_name, client=client)
        self._create_env_vars(
            env_name,
            disable_authentication,
            connections or [],
            client=client,
        )
        return client, group

    def remove_auth_settings(self, env_name):
        secrets_require_remove = [App.AUTH0_CLIENT_ID, App.AUTH0_CLIENT_SECRET]
        for secret_name in secrets_require_remove:
            self.delete_secret(env_name, secret_name)
        envs_require_remove = [App.AUTH0_DOMAIN]
        for app_env_name in envs_require_remove:
            self.delete_env_var(env_name, app_env_name)
        self._get_auth0_instance().clear_up_app(self.app.get_auth_client(env_name))
        self.app.clear_auth_settings(env_name)

    def remove_redundant_env(self, env_name):
        self._get_auth0_instance().clear_up_app(self.app.get_auth_client(env_name))
        self.app.clear_auth_settings(env_name)


# TODO rename to S3Datasource
class S3Bucket(EntityResource):
    """Wraps a S3Bucket model to provide convenience methods for AWS"""

    def __init__(self, bucket):
        self.bucket = bucket
        super(S3Bucket, self).__init__()

    def _init_aws_services(self):
        self.aws_service_class = AWSBucket
        self.aws_bucket_service = self.create_aws_service(self.aws_service_class)

    @classmethod
    def build_folder_path(cls, folder_name):
        """
        Prefix a folder name with the name of the S3 bucket defined in settings.
        """
        return f"{settings.S3_FOLDER_BUCKET_NAME}/{folder_name}"

    @property
    def arn(self):
        return s3_arn(self.bucket.name)

    def _get_assume_role_category(self):
        if self.bucket.is_used_for_app:
            return AWSRoleCategory.app
        else:
            return AWSRoleCategory.user

    def create(self, owner=AWSRoleCategory.user):
        self.aws_bucket_service.assume_role_name = self.get_assume_role(
            self.aws_service_class, aws_role_category=owner
        )
        return self.aws_bucket_service.create(
            self.bucket.name, self.bucket.is_data_warehouse
        )

    def mark_for_archival(self):
        self.aws_bucket_service.assume_role_name = self.get_assume_role(
            self.aws_service_class, aws_role_category=self._get_assume_role_category()
        )
        self.aws_bucket_service.tag_bucket(self.bucket.name, {"to-archive": "true"})

    def exists(self, bucket_name, bucket_owner):
        self.aws_bucket_service.assume_role_name = self.get_assume_role(
            self.aws_service_class, aws_role_category=bucket_owner
        )
        return self.aws_bucket_service.exists(bucket_name)


class S3Folder(S3Bucket):
    def _init_aws_services(self):
        self.aws_service_class = AWSFolder
        self.aws_bucket_service = self.create_aws_service(self.aws_service_class)

    def exists(self, folder_name, bucket_owner):
        folder_path = f"{settings.S3_FOLDER_BUCKET_NAME}/{folder_name}"
        return super().exists(folder_path, bucket_owner), folder_path


class RoleGroup(EntityResource):
    """
    Uses a managed policy as a way to group IAM roles that have access to same
    resources.

    This is because IAM doesn't allow adding roles to IAM groups
    See https://stackoverflow.com/a/48087433/455642
    """

    ENTITY_ASSUME_ROLE_CATEGORY = AWSRoleCategory.user

    def __init__(self, iam_managed_policy):
        super(RoleGroup, self).__init__()
        self.policy = iam_managed_policy

    def _init_aws_services(self):
        self.aws_policy_service = self.create_aws_service(AWSPolicy)

    @property
    def arn(self):
        return iam_arn(f"policy{self.path}{self.policy.name}")

    @property
    def path(self):
        return f"/{settings.ENV}/group/"

    def create(self):
        self.aws_policy_service.create_policy(
            self.policy.name,
            self.policy.path,
        )

    def update_members(self):
        self.aws_policy_service.update_policy_members(
            self.arn,
            {user.iam_role_name for user in self.policy.users.all()},
        )

    def delete(self):
        self.aws_policy_service.delete_policy(self.arn)

    def grant_bucket_access(self, bucket_arn, access_level, path_arns):
        self.aws_policy_service.grant_policy_bucket_access(
            self.arn, bucket_arn, access_level, path_arns
        )

    def revoke_bucket_access(self, bucket_arn):
        self.aws_policy_service.revoke_policy_bucket_access(self.arn, bucket_arn)


class AppParameter(EntityResource):

    ENTITY_ASSUME_ROLE_CATEGORY = AWSRoleCategory.app

    def __init__(self, parameter):
        super(AppParameter, self).__init__()
        self.parameter = parameter

    def _init_aws_services(self):
        self.aws_param_service = self.create_aws_service(AWSParameterStore)

    def create_parameter(self):
        return self.aws_param_service.create_parameter(
            self.parameter.name,
            self.parameter.value,
            self.parameter.role_name,
            self.parameter.description,
        )

    def delete_parameter(self):
        self.aws_param_service.delete_parameter(self.parameter.name)


class ToolDeploymentError(Exception):
    pass


class ToolDeployment:
    def __init__(self, user, tool, old_chart_name=None):
        self.user = user
        self.tool = tool
        self.old_chart_name = old_chart_name

    def __repr__(self):
        return f"<ToolDeployment: {self.tool} {self.user}>"

    @property
    def chart_name(self):
        return self.tool.chart_name

    @property
    def k8s_namespace(self):
        return self.user.k8s_namespace

    @property
    def release_name(self):
        return self.escape_namespace_len(f"{self.chart_name}-{self.user.slug}")

    def escape_namespace_len(self, name: str) -> str:
        return name[: settings.MAX_RELEASE_NAME_LEN]

    def _delete_legacy_release(self):
        """
        At some point the naming scheme for RStudio
        changed. This cause upgrade problems when
        an old release with the old release name is
        present.

        We're going to temporarily check/uninstall
        releases with the old name before installing
        the new release with the correct name.

        We can remove this once every user is on new naming
        scheme for RStudio.
        """
        old_release_name = f"{self.chart_name}-{self.user.slug}"
        old_release_name = self.escape_namespace_len(old_release_name)

        if self.old_chart_name:
            # If an old_chart_name has been passed into the deployment, it
            # means the currently deployed instance of the tool is from a
            # different chart to the one for this tool. Therefore, it's
            # the old_chart_name that we should use for the old release
            # that needs deleting.
            old_release_name = f"{self.old_chart_name}-{self.user.slug}"
            old_release_name = self.escape_namespace_len(old_release_name)

        if old_release_name in helm.list_releases(old_release_name, self.k8s_namespace):
            helm.delete(self.k8s_namespace, old_release_name)

    def _set_values(self, **kwargs):
        """
        Return the list of `--set KEY=VALUE` helm upgrade arguments

        Extracted from `install()` method for clarity.
        """
        values = {
            "username": self.user.username.lower(),
            # XXX backwards compatibility
            "Username": self.user.username.lower(),
            "aws.iamRole": self.user.iam_role_name,
            "toolsDomain": settings.TOOLS_DOMAIN,
        }

        # generate per-deployment secrets
        for key, value in self.tool.values.items():
            if value == "<SECRET_TOKEN>":
                self.tool.values[key] = secrets.token_hex(32)

        values.update(self.tool.values)
        values.update(kwargs)
        set_values = []
        for key, val in values.items():
            if val:
                # Helpful for debugging configs: ignore parameters with missing
                # values and log that the value is missing.
                escaped_val = val.replace(",", "\,")  # noqa : W605
                set_values.extend(["--set", f"{key}={escaped_val}"])
            else:
                log.warning(
                    f"Missing value for helm chart param release - {self.release_name} version - {self.tool.version} namespace - {self.k8s_namespace}, key name - {key}"  # noqa : E501
                )
        return set_values

    def install(self, **kwargs):
        self._delete_legacy_release()

        try:
            set_values = self._set_values(**kwargs)

            return helm.upgrade_release(
                self.release_name,  # release
                # XXX assumes repo name
                f"{settings.HELM_REPO}/{self.chart_name}",  # chart
                "--version",
                self.tool.version,
                "--namespace",
                self.k8s_namespace,
                *set_values,
            )

        except helm.HelmError as error:
            raise ToolDeploymentError(error)

    def uninstall(self, id_token):
        deployment = self.get_deployment(id_token)
        helm.delete(self.k8s_namespace, deployment.metadata.name)

    def restart(self, id_token):
        k8s = KubernetesClient(id_token=id_token)
        return k8s.AppsV1Api.delete_collection_namespaced_replica_set(
            self.k8s_namespace,
            label_selector=(f"app={self.chart_name}"),
        )

    @classmethod
    def is_tool_deployment(cls, metadata):
        """
        Currently the logic for checking whether a deployment is for tool is
        based on the information we put in the deployment yaml, the common info
        cross tools' helm chart is the unidler-key or unide (somehow typo in
        the helm chart :(), we have other alternative field for such check,
        e.g. whether name contains some key words, but IMO, it is too specific.

        We may change this part if we want to refactor how the tool is released
        and managed.
        """
        return metadata.labels.get("unidler-key") is not None or metadata.labels.get(
            "unidle-key"
        )

    @classmethod
    def get_deployments(cls, user, id_token, search_name=None, search_version=None):
        deployments = []
        k8s = KubernetesClient(id_token=id_token)
        results = k8s.AppsV1Api.list_namespaced_deployment(user.k8s_namespace)
        for deployment in results.items:
            if not cls.is_tool_deployment(deployment.metadata):
                continue

            app_name = deployment.metadata.labels["app"]
            _, version = deployment.metadata.labels["chart"].rsplit("-", 1)
            if search_name and search_name not in app_name:
                continue
            if search_version and not version.startswith(search_version):
                continue
            deployments.append(deployment)
        return deployments

    def get_deployment(self, id_token):
        deployments = self.__class__.get_deployments(
            self.user,
            id_token,
            search_name=self.chart_name,
            # search_version=tool_deployment.tool.version,
        )

        if not deployments:
            raise ObjectDoesNotExist(self)

        if len(deployments) > 1:
            log.warning(f"Multiple matches for {self} found")
            raise MultipleObjectsReturned(self)

        return deployments[0]

    def get_status(self, id_token, deployment=None):
        try:
            if deployment is None:
                deployment = self.get_deployment(id_token)

        except ObjectDoesNotExist:
            log.warning(f"{self} not found")
            return TOOL_NOT_DEPLOYED

        except MultipleObjectsReturned:
            log.warning(f"Multiple objects returned for {self}")
            return TOOL_STATUS_UNKNOWN

        conditions = {
            condition.type: condition for condition in deployment.status.conditions
        }

        if "Available" in conditions:
            if conditions["Available"].status == "True":
                if deployment.spec.replicas == 0:
                    return TOOL_IDLED
                return TOOL_READY

        if "Progressing" in conditions:
            progressing_status = conditions["Progressing"].status
            if progressing_status == "True":
                return TOOL_DEPLOYING
            elif progressing_status == "False":
                return TOOL_DEPLOY_FAILED

        log.warning(f"Unknown status for {self}: {deployment.status.conditions}")
        return TOOL_STATUS_UNKNOWN
