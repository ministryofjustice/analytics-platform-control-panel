import structlog
import secrets

from django.conf import settings
from django.core.exceptions import MultipleObjectsReturned, ObjectDoesNotExist
from github import Github, GithubException

from controlpanel.api import auth0, aws
from controlpanel.api.aws import iam_arn, s3_arn  # keep for tests
from controlpanel.api import helm
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


class HomeDirectoryResetError(Exception):
    """
    Raised if a home directory cannot be reset.
    """

    pass


class User:
    """
    Wraps User model to provide convenience methods to access K8S and AWS

    A user is represented by an IAM role, which is assumed by their tools.
    """

    def __init__(self, user):
        self.user = user
        self.k8s_namespace = f"user-{self.user.slug}"
        self.eks_cpanel_namespace = "cpanel"

    @property
    def iam_role_name(self):
        return f"{settings.ENV}_user_{self.user.username.lower()}"

    def _init_user(self):
        if settings.EKS:
            helm.upgrade_release(
                f"bootstrap-user-{self.user.slug}",  # release
                f"{settings.HELM_REPO}/bootstrap-user",  # chart
                f"--set="
                + (
                    f"Username={self.user.slug}"
                ),
            )
            helm.upgrade_release(
                f"provision-user-{self.user.slug}",  # release
                f"{settings.HELM_REPO}/provision-user",  # chart
                f"--namespace={self.k8s_namespace}",
                f"--set="
                + (
                    f"Username={self.user.slug},"
                    f"Efsvolume={settings.EFS_VOLUME},"
                    f"OidcDomain={settings.OIDC_DOMAIN},"
                    f"Email={self.user.email},"
                    f"Fullname={self.user.name},"
                ),
            )
        else:
            helm.upgrade_release(
                f"init-user-{self.user.slug}",  # release
                f"{settings.HELM_REPO}/init-user",  # chart
                f"--set="
                + (
                    f"Env={settings.ENV},"
                    f"NFSHostname={settings.NFS_HOSTNAME},"
                    f"EFSHostname={settings.EFS_HOSTNAME},"
                    f"OidcDomain={settings.OIDC_DOMAIN},"
                    f"Email={self.user.email},"
                    f"Fullname={self.user.name},"
                    f"Username={self.user.slug}"
                ),
            )

    def create(self):
        aws.create_user_role(self.user)

        self._init_user()

        helm.upgrade_release(
            f"config-user-{self.user.slug}",  # release
            f"{settings.HELM_REPO}/config-user",  # chart
            f"--namespace={self.k8s_namespace}",
            f"--set=Username={self.user.slug}",
        )

    def reset_home(self):
        """
        Reset the user's home directory.
        """
        if settings.EKS:
            # On the new EKS infrastructure, the user's home directory[s] is
            # organised differently and on EFS. This is why we use a separate
            # helm chart.
            helm.upgrade_release(
                f"reset-user-efs-home-{self.user.slug}",  # release
                f"{settings.HELM_REPO}/reset-user-efs-home",  # chart
                f"--namespace=user-{self.user.slug}",
                f"--set=Username={self.user.slug}",
            )
        else:
            helm.upgrade_release(
                f"reset-user-home-{self.user.slug}",  # release
                f"{settings.HELM_REPO}/reset-user-home",  # chart
                f"--namespace=user-{self.user.slug}",
                f"--set=Username={self.user.slug}",
            )

    def delete(self):
        aws.delete_role(self.user.iam_role_name)
        releases = helm.list_releases(namespace=self.k8s_namespace)
        # Delete all the user initialisation charts.
        if not settings.EKS:
            releases.append(f"init-user-{self.user.slug}")
        releases.append(f"bootstrap-user-{self.user.slug}")
        releases.append(f"provision-user-{self.user.slug}")
        if settings.EKS:
            helm.delete_eks(self.k8s_namespace, *releases)
        else:
            helm.delete(*releases)

    def grant_bucket_access(self, bucket_arn, access_level, path_arns=[]):
        aws.grant_bucket_access(
            self.iam_role_name, bucket_arn, access_level, path_arns
        )

    def revoke_bucket_access(self, bucket_arn):
        aws.revoke_bucket_access(self.iam_role_name, bucket_arn)

    def on_authenticate(self):
        """
        Run on each authenticated login on the control panel. Checks if the
        expected helm charts exist for the user. If not, will set things up
        properly. This function also checks if the user is ready to migrate
        and is logged into the new EKS infrastructure. If so, runs all the
        charts and AWS updates to cause the migration to be fulfilled.
        """
        init_chart_name = f"init-user-{self.user.slug}"
        bootstrap_chart_name = f"bootstrap-user-{self.user.slug}"
        provision_chart_name = f"provision-user-{self.user.slug}"
        releases = set(helm.list_releases(namespace=self.k8s_namespace))

        if not settings.EKS:
            # On the old infrastructure...
            if init_chart_name not in releases:
                # The user has their charts deleted, so recreate.
                log.warning(f"Re-running init user chart for {self.user.slug}")
                self._init_user()

            return

        # On the new cluster, check if the bootstrap/provision helm
        # charts exist. If not, this is the user's first login to the new
        # platform. Run these helm charts to migrate the user to the new
        # platform. Ensure this is all stored in the database in case they
        # try to log into the control panel on the old infrastructure.
        bootstrap_releases = set(helm.list_releases(namespace=self.eks_cpanel_namespace, release=bootstrap_chart_name))
        has_charts = (
            bootstrap_chart_name in bootstrap_releases
            and
            provision_chart_name in releases
        )

        if self.user.migration_state == self.user.COMPLETE:
            # If the authenticated user has already migrated to this EKS system,
            # then we just want to check that they have previously run the required
            # charts before returning
            if not has_charts:
                # User has migrated but for some reason has no charts so we should re-init them.
                log.info(f"User {self.user.slug} already migrated but has no charts, initialising")
                self._init_user()

            return

        # User's migration state is not yet marked as complete, and so we
        # need to migrate their AWS role before running the init-user
        # helm charts before marked it as such
        log.info(f"Starting to migrate user {self.user.slug} from {self.user.migration_state}")

        self.user.migration_state = self.user.MIGRATING
        self.user.save()

        # Migrate the AWS roles for the user.
        aws.migrate_user_role(self.user)

        # Run the new charts to configure the user for EKS infra.
        self._init_user()

        # Update the user's state in the database.
        self.user.migration_state = self.user.COMPLETE
        self.user.save()

        log.info(f"Completed migration of user {self.user.slug}")


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
        aws.grant_bucket_access(
            self.iam_role_name, bucket_arn, access_level, path_arns
        )

    def revoke_bucket_access(self, bucket_arn):
        aws.revoke_bucket_access(self.iam_role_name, bucket_arn)

    def delete(self):
        aws.delete_role(self.iam_role_name)
        auth0.ExtendedAuth0().clear_up_app(app_name=self.app.slug, group_name=self.app.slug)

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
        return aws.create_bucket(
            self.bucket.name, self.bucket.is_data_warehouse
        )

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
        return f"/{settings.ENV}/group/"

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
        aws.grant_group_bucket_access(
            self.arn, bucket_arn, access_level, path_arns
        )

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
            log.warning(
                f"Failed getting {name} Github org repos for {user}: {err}"
            )
            raise err
    return repos


def get_repository(user, repo_name):
    github = Github(user.github_api_token)
    try:
        return github.get_repo(repo_name)
    except GithubException.UnknownObjectException:
        log.warning(
            f"Failed getting {repo_name} Github repo for {user}: {err}"
        )
        return None


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
        if settings.EKS:
            old_release_name = f"{self.chart_name}-{self.user.slug}"
            if self.old_chart_name:
                # If an old_chart_name has been passed into the deployment, it
                # means the currently deployed instance of the tool is from a
                # different chart to the one for this tool. Therefore, it's
                # the old_chart_name that we should use for the old release
                # that needs deleting.
                old_release_name = f"{self.old_chart_name}-{self.user.slug}"
            if old_release_name in helm.list_releases(old_release_name, self.k8s_namespace):
                helm.delete_eks(self.k8s_namespace, old_release_name)
        else:
            old_release_name = f"{self.user.slug}-{self.chart_name}"
            if old_release_name in helm.list_releases(old_release_name):
                helm.delete(old_release_name)

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
            if val: # Helpful for debugging configs: ignore parameters with missing values and log that the value is missing.
                escaped_val = val.replace(",", "\,")
                set_values.extend(["--set", f"{key}={escaped_val}"])
            else:
                log.warning(f"Missing value for helm chart param release - {self.release_name} version - {self.tool.version} namespace - {self.k8s_namespace}, key name - {key}")
        return set_values

    def install(self, **kwargs):
        self._delete_legacy_release()

        try:
            set_values = self._set_values(**kwargs)

            return helm.upgrade_release(
                self.release_name,  # release
                # XXX assumes repo name
                f"{settings.HELM_REPO}/{self.chart_name}",  # chart
                f"--version",
                self.tool.version,
                f"--namespace",
                self.k8s_namespace,
                *set_values,
            )

        except helm.HelmError as error:
            raise ToolDeploymentError(error)

    def uninstall(self, id_token):
        deployment = self.get_deployment(id_token)
        if settings.EKS:
            helm.delete_eks(self.k8s_namespace, deployment.metadata.name)
        else:
            helm.delete(
                deployment.metadata.name,
                f"--namespace={self.k8s_namespace}"
            )

    def restart(self, id_token):
        k8s = KubernetesClient(id_token=id_token)
        return k8s.AppsV1Api.delete_collection_namespaced_replica_set(
            self.k8s_namespace,
            label_selector=(f"app={self.chart_name}"),
        )

    @classmethod
    def get_deployments(
        cls, user, id_token, search_name=None, search_version=None
    ):
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
            _, chart_version = deployment.metadata.labels["chart"].rsplit(
                "-", 1
            )
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
            condition.type: condition
            for condition in deployment.status.conditions
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

        log.warning(
            f"Unknown status for {self}: {deployment.status.conditions}"
        )
        return TOOL_STATUS_UNKNOWN
