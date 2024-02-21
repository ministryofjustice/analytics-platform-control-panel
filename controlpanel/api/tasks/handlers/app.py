# First-party/Local
from controlpanel.api import cluster
from controlpanel.api.models import App, User
from controlpanel.api.tasks.handlers.base import BaseModelTaskHandler


class CreateAppAuthSettings(BaseModelTaskHandler):
    model = App
    name = "create_app_auth_settings"

    def handle(self, envs, disable_authentication, connections):
        task_user = User.objects.filter(pk=self.task_user_pk).first()
        if not task_user or not task_user.github_api_token:
            # TODO maybe log this as something has gone wrong?
            return self.complete()

        for env in envs:
            cluster.App(self.object, task_user.github_api_token).create_auth_settings(
                env_name=env,
                disable_authentication=disable_authentication,
                connections=connections,
            )
        self.complete()


class CreateAppAWSRole(BaseModelTaskHandler):
    model = App
    name = "create_app_aws_role"

    def handle(self):
        task_user = User.objects.filter(pk=self.task_user_pk).first()
        cluster.App(self.object, task_user.github_api_token).create_iam_role()
        self.complete()
