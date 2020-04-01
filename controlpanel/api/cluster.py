import logging
import secrets

from django.conf import settings
from django.core.exceptions import MultipleObjectsReturned, ObjectDoesNotExist
from github import Github, GithubException

from controlpanel.api import auth0, aws
from controlpanel.api.aws import iam_arn, s3_arn  # keep for tests
from controlpanel.api.helm import HelmError, helm
from controlpanel.api.kubernetes import KubernetesClient
from controlpanel.utils import github_repository_name


log = logging.getLogger(__name__)


TOOL_DEPLOYING = 'Deploying'
TOOL_DEPLOY_FAILED = 'Failed'
TOOL_IDLED = 'Idled'
TOOL_NOT_DEPLOYED = 'Not deployed'
TOOL_READY = 'Ready'
TOOL_UPGRADED = 'Upgraded'
TOOL_STATUS_UNKNOWN = 'Unknown'


class User:
    """
    Wraps User model to provide convenience methods to access K8S and AWS

    A user is represented by an IAM role, which is assumed by their tools.
    """
    def __init__(self, user):
        self.user = user
        self.k8s_namespace = f'user-{self.user.slug}'

    @property
    def iam_role_name(self):
        return f'{settings.ENV}_user_{self.user.username.lower()}'

    def create(self):
        aws.create_user_role(self.user)

        helm.upgrade_release(
            f"init-user-{self.user.slug}",
            f"{settings.HELM_REPO}/init-user",
            f"--set=" + (
                f"Env={settings.ENV},"
                f"NFSHostname={settings.NFS_HOSTNAME},"
                f"OidcDomain={settings.OIDC_DOMAIN},"
                f"Email={self.user.email},"
                f"Fullname={self.user.name},"
                f"Username={self.user.slug}"
            ),
        )
        helm.upgrade_release(
            f"config-user-{self.user.slug}",
            f"{settings.HELM_REPO}/config-user",
            f"--namespace={self.k8s_namespace}",
            f"--set=Username={self.user.slug}",
        )

    def delete(self):
        aws.delete_role(self.user.iam_role_name)
        helm.delete(helm.list_releases(f"--namespace={self.k8s_namespace}"))
        helm.delete(f"init-user-{self.user.slug}")

    def grant_bucket_access(self, bucket_arn, access_level, path_arns=[]):
        aws.grant_bucket_access(self.iam_role_name, bucket_arn, access_level, path_arns)

    def revoke_bucket_access(self, bucket_arn):
        aws.revoke_bucket_access(self.iam_role_name, bucket_arn)


class App:
    """
    Responsible for the apps-related interactions with the k8s cluster and AWS
    """

    APPS_NS = "apps-prod"

    def __init__(self, app):
        self.app = app

    @property
    def iam_role_name(self):
        return f"{settings.ENV}_app_{self.app.slug}"

    def create_iam_role(self):
        aws.create_app_role(self.app)

    def grant_bucket_access(self, bucket_arn, access_level, path_arns):
        aws.grant_bucket_access(self.iam_role_name, bucket_arn, access_level, path_arns)

    def revoke_bucket_access(self, bucket_arn):
        aws.revoke_bucket_access(self.iam_role_name, bucket_arn)

    def delete(self):
        aws.delete_role(self.iam_role_name)
        auth0.AuthorizationAPI().delete_group(group_name=self.app.slug)
        helm.delete(True, self.app.release_name)

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


class S3Bucket:
    """Wraps a S3Bucket model to provide convenience methods for AWS"""
    def __init__(self, bucket):
        self.bucket = bucket

    @property
    def arn(self):
        return s3_arn(self.bucket.name)

    def create(self):
        return aws.create_bucket(self.bucket.name, self.bucket.is_data_warehouse)

    def mark_for_archival(self):
        aws.tag_bucket(self.bucket.name, {"to-archive": "true"})


class RoleGroup:
    """
    Uses a managed policy as a way to group IAM roles that have access to same
    resources.

    This is because IAM doesn't allow adding roles to IAM groups
    See https://stackoverflow.com/a/48087433/455642
    """
    def __init__(self, iam_managed_policy):
        self.policy = iam_managed_policy

    @property
    def arn(self):
        return iam_arn(f"policy{self.path}{self.policy.name}")

    @property
    def path(self):
        return f'/{settings.ENV}/group/'

    def create(self):
        aws.create_group(
            self.policy.name,
            self.policy.path,
        )

    def update_members(self):
        aws.update_group_members(
            self.arn,
            {user.iam_role_name for user in self.policy.users.all()},
        )

    def delete(self):
        aws.delete_group(self.arn)

    def grant_bucket_access(self, bucket_arn, access_level, path_arns):
        aws.grant_group_bucket_access(self.arn, bucket_arn, access_level, path_arns)

    def revoke_bucket_access(self, bucket_arn):
        aws.revoke_group_bucket_access(self.arn, bucket_arn)


def create_parameter(name, value, role, description):
    return aws.create_parameter(name, value, role, description)


def delete_parameter(name):
    aws.delete_parameter(name)


def list_role_names():
    return aws.list_role_names()


def get_repositories(user):
    repos = []
    github = Github(user.github_api_token)
    for name in settings.GITHUB_ORGS:
        try:
            org = github.get_organization(name)
            repos.extend(org.get_repos())
        except GithubException as err:
            log.warning(f'Failed getting {name} Github org repos for {user}: {err}')
            raise err
    return repos


def get_repository(user, repo_name):
    github = Github(user.github_api_token)
    try:
        return github.get_repo(repo_name)
    except GithubException.UnknownObjectException:
        log.warning(f'Failed getting {repo_name} Github repo for {user}: {err}')
        return None


class ToolDeploymentError(Exception):
    pass


class ToolDeployment():

    def __init__(self, user, tool):
        self.user = user
        self.tool = tool

    def __repr__(self):
        return f'<ToolDeployment: {self.tool!r} {self.user!r}>'

    @property
    def chart_name(self):
        return self.tool.chart_name

    @property
    def k8s_namespace(self):
        return self.user.k8s_namespace

    @property
    def release_name(self):
        return f"{self.chart_name}-{self.user.slug}"

    def install(self, **kwargs):
        values = {
            "username": self.user.username.lower(),
            "Username": self.user.username.lower(),  # XXX backwards compatibility
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
            escaped_val = val.replace(',', '\,')
            set_values.extend(['--set', f'{key}={escaped_val}'])

        try:
            return helm.upgrade_release(
                self.release_name,
                f'{settings.HELM_REPO}/{self.chart_name}',  # XXX assumes repo name
                # f'--version', tool.version,
                f'--namespace', self.k8s_namespace,
                *set_values,
            )

        except HelmError as error:
            raise ToolDeploymentError(error)

    def uninstall(self, id_token):
        deployment = self.get_deployment(id_token)
        helm.delete(
            deployment.metadata.name,
            f"--namespace={self.k8s_namespace}",
        )

    def restart(self, id_token):
        k8s = KubernetesClient(id_token=id_token)
        return k8s.AppsV1Api.delete_collection_namespaced_replica_set(
            self.k8s_namespace,
            label_selector=(
                f"app={self.chart_name}"
                # f'-{tool_deployment.tool.version}'
            ),
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
            log.warning(f"Multiple matches for {self!r} found")
            raise MultipleObjectsReturned(self)

        return deployments[0]

    def get_status(self, id_token):
        try:
            deployment = self.get_deployment(id_token)

        except ObjectDoesNotExist:
            log.warning(f"{self!r} not found")
            return TOOL_NOT_DEPLOYED

        except MultipleObjectsReturned:
            log.warning(f"Multiple objects returned for {self!r}")
            return TOOL_STATUS_UNKNOWN

        conditions = {
            condition.type: condition
            for condition in deployment.status.conditions
        }

        if "Available" in conditions:
            if conditions["Available"].status == "True":
                if deployment.spec.replicas == 0:
                    return TOOL_IDLED
                return TOOL_READY

        if 'Progressing' in conditions:
            progressing_status = conditions['Progressing'].status
            if progressing_status == "True":
                return TOOL_DEPLOYING
            elif progressing_status == "False":
                return TOOL_DEPLOY_FAILED

        log.warning(
            f"Unknown status for {self!r}: {deployment.status.conditions}"
        )
        return TOOL_STATUS_UNKNOWN
