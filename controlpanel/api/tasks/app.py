# Third-party
from django.conf import settings

# First-party/Local
from controlpanel.api.tasks.task_base import TaskBase


class AppCreateRole(TaskBase):
    ENTITY_CLASS = "App"
    QUEUE_NAME = settings.IAM_QUEUE_NAME

    @property
    def task_name(self):
        return "create_app_aws_role"

    @property
    def task_description(self):
        return "creating aws role"


class AppCreateAuth(AppCreateRole):

    QUEUE_NAME = settings.AUTH_QUEUE_NAME

    @property
    def task_name(self):
        return "create_app_auth_settings"

    def _get_args_list(self):
        return [
            self.entity.id,
            self.user.id if self.user else 'None',
            self.extra_data.get('deployment_envs'),
            self.extra_data.get('disable_authentication'),
            self.extra_data.get('connections'),
            # self.extra_data.get('has_ip_ranges') # NOT USED, REMOVE IT?
        ]

    @property
    def task_description(self):
        return "creating auth settings"
