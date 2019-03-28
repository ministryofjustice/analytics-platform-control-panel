from collections import UserDict
import secrets

from django.conf import settings
from django.utils.functional import cached_property
from rest_framework.exceptions import APIException

from controlpanel.api.helm import Helm
from controlpanel.kubeapi.views import client


IDLED = "mojanalytics.xyz/idled"

SUPPORTED_TOOL_NAMES = list(settings.TOOLS.keys())


class DuplicateTool(Exception):
    pass


class ToolNotDeployed(APIException):
    status_code = 400
    default_detail = f"Specified tool not deployed"
    default_code = "tool_not_deployed"


class UnsupportedToolException(APIException):
    status_code = 400
    supported = ", ".join(SUPPORTED_TOOL_NAMES)
    default_detail = f"Unsupported tool, must be one of: {supported}"
    default_code = "unsupported_tool"


class ToolRepository(UserDict):

    def __getitem__(self, key):
        if key not in self.tools:
            raise UnsupportedToolException(key)

        if key not in self.tools:
            raise UnsupportedToolException(key)

        return super().__getitem__(key)

    def __setitem__(self, key, value):
        if key not in SUPPORTED_TOOL_NAMES:
            raise UnsupportedToolException(key)

        if key in self.tools:
            raise DuplicateTool(key)

        super().__setitem__(key, value)


class ToolMeta(type):
    """Adds Tool subclasses to repository"""

    # repository is shared across all Tool subclasses
    _repository = ToolRepository()

    def __init__(cls, name, bases, clsdict):
        super().__init__(name, bases, clsdict)
        if 'name' not in clsdict:
            raise AttributeError(f"{name}.name")
        if name != "Tool":
            cls._repository[clsdict['name']] = cls


class Tool(metaclass=ToolMeta):
    name = None

    @classmethod
    def create(cls, name):
        return cls.repository[name]()

    @cached_property
    def helm(self):
        return Helm()

    @property
    def chart_name(self):
        return f"mojanalytics/{self.name}"

    def release_name(self, username):
        return f"{username}-{self.name}"

    def deploy_params(self, user):
        conf = settings.TOOLS[self.name]
        return {
            "username": user.username.lower(),
            "aws.iamRole": user.iam_role_name,
            "toolsDomain": settings.TOOLS_DOMAIN,
            "authProxy.cookieSecret": secrets.token_hex(32),
            f"{self.name}.secureCookieKey": secrets.token_hex(32),
            "authProxy.auth0.domain": conf["domain"],
            "authProxy.auth0.clientId": conf["client_id"],
            "authProxy.auth0.clientSecret": conf["client_secret"],
        }

    def deploy_for(self, user):
        """
        Deploy the given tool in the user namespace.
        >>> class RStudio(BaseTool):
        ...     name = 'rstudio'
        >>> rstudio = RStudio()
        >>> rstudio.deploy_for(alice)
        """

        username = user.username.lower()
        params = self.deploy_params(user)
        if params:
            params = [
                "--set",
                ",".join(f"{key}={val}" for key, val in params.items()),
            ]
        return self.helm.upgrade_release(
            self.release_name(username),
            self.chart_name,
            f"--namespace={user.k8s_namespace}",
            *params,
        )

    def get_user_deployment(self, user):
        deployments = client.AppsV1Api().list_namespaced_deployment(
            namespace=user.k8s_namespace,
            label_selector=f"app={self.name}"
        )

        if len(deployments.items) < 1:
            raise ToolNotDeployed()

        return ToolDeployment(deployments.items[0], user)


class RStudio(Tool):
    name = "rstudio"


class JupyterLab(Tool):
    name = "jupyter-lab"

    def release_name(self, username):
        return f"{self.name}-{username}"

    def deploy_params(self, user):
        conf = settings.TOOLS[self.name]
        return {
            "Username": user.username.lower(),
            "aws.iamRole": user.iam_role_name,
            "toolsDomain": settings.TOOLS_DOMAIN,
            "cookie_secret": secrets.token_hex(32),
            "authProxy.auth0_domain": conf["domain"],
            "authProxy.auth0_client_id": conf["client_id"],
            "authProxy.auth0_client_secret": conf["client_secret"],
        }


class ToolDeployment(object):

    def __init__(self, deployment, user):
        self.deployment = deployment
        self.user = user

    @classmethod
    def list(cls, user):
        deployments = client.AppsV1Api().list_namespaced_deployment(
            user.k8s_namespace,
        )
        return [
            ToolDeployment(deployment, user) for deployment in deployments.items
        ]

    @property
    def name(self):
        return self.deployment.metadata.labels["app"]

    @property
    def username(self):
        return self.user.username.lower()

    @property
    def url(self):
        return f"https://{self.username}-{self.name}.{settings.TOOLS_DOMAIN}"

    @property
    def pods(self):
        pods = client.CoreV1Api().list_namespaced_pod(
            self.user.k8s_namespace,
            label_selector=f"app={self.name}",
        )
        return [Pod(pod) for pod in pods.items]

    @property
    def available(self):
        return any(pod.status["phase"] == "Running" for pod in self.pods)

    @property
    def idled(self):
        return self.deployment.metadata.labels.get(IDLED) == "true"

    def restart(self):
        return client.AppsV1Api().delete_collection_namespaced_replica_set(
            namespace=self.user.k8s_namespaces,
            label_selector=f"app={self.name}",
            watch=True,
        )


class Pod(object):

    def __init__(self, pod):
        self.pod = pod

    @property
    def status(self):

        if self.pod.status.container_status:
            state = self.pod.status.container_status[0].state

            if state.waiting:
                return {"phase": "waiting", "reason": state.waiting.reason}

            if state.terminated:
                if not state.terminated.reason:
                    if state.terminated.signal:
                        reason = f"Signal:{state.terminated.signal}"
                    else:
                        reason = f"ExitCode:{state.terminated.exit_code}"
                return {"phase": "terminated", "reason": reason}

        return {"phase": self.pod.status.phase}

    @property
    def display_status(self):
        status = self.status
        reason = f":{status['reason']}" if status.get("reason") else ""
        return f"{status['phase']}{reason}"
