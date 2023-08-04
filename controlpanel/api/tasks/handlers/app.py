from controlpanel.api import cluster
from controlpanel.api.models import App
from controlpanel.api.tasks.handlers.base import BaseModelTaskHandler


class CreateAppAuthSettings(BaseModelTaskHandler):
    model = App
    name = "create_app_auth_settings"
    permission_required = "api.create_app"

    def has_permission(self, user, obj=None):
        if not user.github_api_token:
            return False
        return super().has_permission(user, obj)

    def run_task(self, app, user, envs, disable_authentication, connections):
        for env in envs:
            cluster.App(app, user.github_api_token).create_auth_settings(
                env_name=env,
                disable_authentication=disable_authentication,
                connections=connections,
            )
        self.complete()


class CreateAppAWSRole(BaseModelTaskHandler):
    model = App
    name = "create_app_aws_role"
    permission_required = "api.create_app"

    def run_task(self, app, user):
        cluster.App(app).create_iam_role()
        self.complete()
