# Standard library
import os
import secrets
from copy import deepcopy
from typing import List

# Third-party
import structlog
from django.conf import settings
from django.core.exceptions import MultipleObjectsReturned, ObjectDoesNotExist

# First-party/Local
from controlpanel.api import helm
from controlpanel.api.aws import (
    AWSBucket,
    AWSParameterStore,
    AWSPolicy,
    AWSRole,
    AWSSecretManager,
    iam_arn,
    iam_assume_role_principal,
    s3_arn,
)
from controlpanel.api.kubernetes import KubernetesClient
from controlpanel.utils import github_repository_name

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

AWS_ROLE_CATEGORY_APP = "APP"
AWS_ROLE_CATEGORY_USER = "USER"


BASE_ASSUME_ROLE_POLICY = {
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
                "AWS": iam_assume_role_principal(),
            },
            "Action": "sts:AssumeRole",
        },
    ],
}


class HomeDirectoryResetError(Exception):
    """
    Raised if a home directory cannot be reset.
    """

    pass


class AWSServiceCredentialSettings:
    """This class is responsible for defining the mapping between coding object (class[.func] or function) for creating # noqa : E501
    AWS resource or using AWS service for achieving something. The setting may be imported through external source e.g. # noqa : E501
    config yaml file or db in the future, such process will be outside this class for now, only the json object will be # noqa : E501
    pass in. The assumed json structure is 2 level dictionary as below:
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
        policy["Statement"].append(User.SAML_STATEMENT)
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
        # Removed those initially installed charts from the charts which are retrieved from the namespace # noqa : E501
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
        self._uninstall_helm_charts(self.k8s_namespace, init_installed_charts, dry_run=dry_run)

        # Only remove the installed charts from cpanel namespace
        init_installed_charts = self._filter_out_installation_charts(cpanel_releases)
        self._uninstall_helm_charts(self.eks_cpanel_namespace, init_installed_charts, dry_run=dry_run)

    def delete(self):
        self.aws_role_service.delete_role(self.user.iam_role_name)
        self.delete_user_helm_charts()

    def grant_bucket_access(self, bucket_arn, access_level, path_arns=[]):
        self.aws_role_service.grant_bucket_access(
            self.iam_role_name, bucket_arn, access_level, path_arns
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

    def on_authenticate(self):
        """
        Run on each authenticated login on the control panel.
        This function also checks whether the users has all those charts installed or not # noqa : E501
        """
        if not self.has_required_installation_charts():
            # For some reason, user does not have all the charts required so we should re-init them. # noqa : E501
            log.info(
                f"User {self.user.slug} already migrated but has no charts, initialising"  # noqa : E501
            )
            self.delete_user_helm_charts()
            self._init_user()


class App(EntityResource):
    """
    Responsible for the apps-related interactions with the k8s cluster and AWS
    """

    APPS_NS = "apps-prod"
    secret_type = "auth"

    def __init__(self, app):
        super(App, self).__init__()
        self.app = app

    def _init_aws_services(self):
        self.aws_role_service = self.create_aws_service(AWSRole)
        self.aws_secret_service = self.create_aws_service(AWSSecretManager)

    def set_secret_type(self, type_key: str) -> "App":
        self.secret_type = type_key
        return self

    @property
    def _get_secret_uri(self) -> str:
        return self.app.get_secret_key(self.secret_type)

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
        self.delete_secret()

    @property
    def url(self):
        k8s = KubernetesClient(use_cpanel_creds=True)

        repo_name = github_repository_name(self.app.repo_url)
        ingresses = k8s.ExtensionsV1beta1Api.list_namespaced_ingress(
            self.APPS_NS,
            label_selector=f"repo={repo_name}",
        ).items

        if len(ingresses) != 1:
            return None

        return f"https://{ingresses[0].spec.rules[0].host}"

    def list_role_names(self):
        return self.aws_role_service.list_role_names()

    def create_or_update_secret(self, secret_data):
        self.aws_secret_service.create_or_update(
            secret_name=self._get_secret_uri, secret_data=secret_data
        )

    def delete_secret(self):
        self.aws_secret_service.delete_secret(secret_name=self._get_secret_uri)

    def delete_entries_in_secret(self, keys_to_delete: List[str]) -> bool:
        return self.aws_secret_service.delete_keys_in_secret(
            secret_name=self._get_secret_uri, keys_to_delete=keys_to_delete
        )

    def get_secret_if_found(self):
        return self.aws_secret_service.get_secret_if_found(self._get_secret_uri)


class S3Bucket(EntityResource):
    """Wraps a S3Bucket model to provide convenience methods for AWS"""

    def __init__(self, bucket):
        super(S3Bucket, self).__init__()
        self.bucket = bucket

    def _init_aws_services(self):
        self.aws_bucket_service = self.create_aws_service(AWSBucket)

    @property
    def arn(self):
        return s3_arn(self.bucket.name)

    def _get_assume_role_category(self):
        if self.bucket.is_used_for_app:
            return AWS_ROLE_CATEGORY_APP
        else:
            return AWS_ROLE_CATEGORY_USER

    def create(self, owner=AWS_ROLE_CATEGORY_USER):
        self.aws_bucket_service.assume_role_name = self.get_assume_role(
            AWSBucket, aws_role_category=owner
        )
        return self.aws_bucket_service.create_bucket(
            self.bucket.name, self.bucket.is_data_warehouse
        )

    def mark_for_archival(self):
        self.aws_bucket_service.assume_role_name = self.get_assume_role(
            AWSBucket, aws_role_category=self._get_assume_role_category()
        )
        self.aws_bucket_service.tag_bucket(self.bucket.name, {"to-archive": "true"})

    def has_existed(self, bucket_name, bucket_owner):
        self.aws_bucket_service.assume_role_name = self.get_assume_role(
            AWSBucket, aws_role_category=bucket_owner
        )
        return self.aws_bucket_service.has_existed(bucket_name)


class RoleGroup(EntityResource):
    """
    Uses a managed policy as a way to group IAM roles that have access to same
    resources.

    This is because IAM doesn't allow adding roles to IAM groups
    See https://stackoverflow.com/a/48087433/455642
    """

    ENTITY_ASSUME_ROLE_CATEGORY = AWS_ROLE_CATEGORY_USER

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

    ENTITY_ASSUME_ROLE_CATEGORY = AWS_ROLE_CATEGORY_APP

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
        return f"{self.chart_name}-{self.user.slug}"

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
        if self.old_chart_name:
            # If an old_chart_name has been passed into the deployment, it
            # means the currently deployed instance of the tool is from a
            # different chart to the one for this tool. Therefore, it's
            # the old_chart_name that we should use for the old release
            # that needs deleting.
            old_release_name = f"{self.old_chart_name}-{self.user.slug}"
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
            if (
                val
            ):  # Helpful for debugging configs: ignore parameters with missing values and log that the value is missing. # noqa : E501
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
    def get_deployments(cls, user, id_token, search_name=None, search_version=None):
        deployments = []
        k8s = KubernetesClient(id_token=id_token)
        results = k8s.AppsV1Api.list_namespaced_deployment(user.k8s_namespace)
        for deployment in results.items:
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

    def get_installed_chart_version(self, id_token):
        """
        Returns the installed helm chart version of the tool

        This is extracted from the `chart` label in the corresponding
        `Deployment`.
        """

        try:
            deployment = self.get_deployment(id_token)
            _, chart_version = deployment.metadata.labels["chart"].rsplit("-", 1)
            return chart_version
        except ObjectDoesNotExist:
            return None

    def get_status(self, id_token):
        try:
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
