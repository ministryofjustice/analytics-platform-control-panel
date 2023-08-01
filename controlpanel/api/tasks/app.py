from controlpanel.api.tasks.task_base import TaskBase


class AppCreateRole(TaskBase):
    ENTITY_CLASS = "App"

    @property
    def task_name(self):
        return "controlpanel.celery.create_app_role"

    @property
    def task_description(self):
        return "creating aws role"


class AppCreateAuth(AppCreateRole):

    # QUEUE_NAME = "auth_queue"

    @property
    def task_name(self):
        return "controlpanel.celery.create_auth_settings"

    def _get_args_list(self):
        return [
            self.entity.id,
            self.user.id,
            self.extra_data.get('deployment_envs'),
            self.extra_data.get('disable_authentication'),
            self.extra_data.get('connections'),
            self.extra_data.get('has_ip_ranges')
        ]

    @property
    def task_description(self):
        return "creating auth settings"
