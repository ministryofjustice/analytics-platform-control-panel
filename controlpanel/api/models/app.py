# Standard library
import json
import uuid

# Third-party
from auth0.exceptions import Auth0Error
from django.conf import settings
from django.db import models
from django_extensions.db.fields import AutoSlugField
from django_extensions.db.models import TimeStampedModel

# First-party/Local
from controlpanel.api import auth0, cluster, tasks
from controlpanel.api.models import IPAllowlist
from controlpanel.utils import github_repository_name, s3_slugify, webapp_release_name


class App(TimeStampedModel):
    name = models.CharField(max_length=100, blank=False)
    description = models.TextField(blank=True)
    slug = AutoSlugField(populate_from="_repo_name", slugify_function=s3_slugify)
    repo_url = models.URLField(max_length=512, blank=False, unique=True)
    created_by = models.ForeignKey("User", on_delete=models.SET_NULL, null=True)
    ip_allowlists = models.ManyToManyField(
        IPAllowlist,
        through="AppIPAllowList",
        related_name="apps",
        related_query_name="app",
        blank=True,
    )
    res_id = models.UUIDField(unique=True, default=uuid.uuid4, editable=False)

    # The app_conf mainly for storing the auth settings related and those information
    # are not within the fields which will be searched frequently
    app_conf = models.JSONField(null=True)

    # Stores the Cloud Platform namespace name
    namespace = models.CharField(unique=True, max_length=63)

    # Non database field just for passing extra parameters
    disable_authentication = False
    connections = {}
    current_user = None
    deployment_envs = []
    has_ip_ranges = False

    DEFAULT_AUTH_CATEGORY = "primary"
    KEY_WORD_FOR_AUTH_SETTINGS = "auth_settings"

    DEFAULT_SETTING_KEY_WORD = "DEFAULT"

    class Meta:
        db_table = "control_panel_api_app"
        ordering = ("name",)

    def __init__(self, *args, **kwargs):
        """Overwrite this constructor to pass some non-field parameter"""
        self.disable_authentication = kwargs.pop("disable_authentication", False)
        self.connections = kwargs.pop("connections", {})
        self.current_user = kwargs.pop("current_user", None)
        self.deployment_envs = kwargs.pop("deployment_envs", [])
        self.has_ip_ranges = kwargs.pop("has_ip_ranges", False)
        super().__init__(*args, **kwargs)

    def __repr__(self):
        return f"<App: {self.slug}>"

    @property
    def admins(self):
        return [ua.user for ua in self.userapps.filter(is_admin=True)]

    @property
    def iam_role_name(self):
        return cluster.App(self).iam_role_name

    @property
    def _repo_name(self):
        return github_repository_name(self.repo_url)

    @property
    def release_name(self):
        return webapp_release_name(self._repo_name)

    @property
    def iam_role_arn(self):
        return cluster.iam_arn(f"role/{self.iam_role_name}")

    def get_group_id(self, env_name):
        return self.get_auth_client(env_name).get("group_id")

    def customers(self, env_name=None):
        return (
            auth0.ExtendedAuth0().groups.get_group_members(group_id=self.get_group_id(env_name)) or []
        )

    def customer_paginated(self, page, group_id, per_page=25):
        return (
            auth0.ExtendedAuth0().groups.get_group_members_paginated(
                group_id, page=page, per_page=per_page
            )
            or []
        )

    def auth0_connections(self, env_name):
        client_id = self.get_auth_client(env_name).get("client_id")
        connections = auth0.ExtendedAuth0().get_client_enabled_connections([client_id])
        return connections.get(client_id) or []

    def auth0_connections_by_env(self):
        connections = {}
        client_ids = []
        client_env_mapping = {}
        for env_name, client_info in ((self.app_conf or {}).get(
                self.KEY_WORD_FOR_AUTH_SETTINGS) or {}).items():
            connections[env_name] = dict(client_id=client_info.get('client_id'))
            if client_info.get('client_id'):
                client_env_mapping[client_info["client_id"]] = env_name
                client_ids.append(client_info.get('client_id'))
        returned_connections = auth0.ExtendedAuth0().get_client_enabled_connections(client_ids)
        for client_id, client_connections in returned_connections.items():
            env_name = client_env_mapping.get(client_id)
            if env_name:
                connections[env_name].update(dict(
                    connections=returned_connections.get(client_id)
                ))
        return connections

    def auth0_clients_status(self):
        """ Check the status of the auth0-clients stored in the app_conf field"""
        status = {}
        for env_name, client_info in ((self.app_conf or {}).get(
                self.KEY_WORD_FOR_AUTH_SETTINGS) or {}).items():
            if client_info.get('client_id'):
                try:
                    auth0.ExtendedAuth0().clients.get(client_info.get('client_id'))
                    status[env_name] ={
                        "client_id": client_info.get('client_id'),
                        "ok": True
                    }
                except Auth0Error as error:
                    status[env_name] ={
                        "client_id": client_info.get('client_id'),
                        "ok": False,
                        "error_msg": error.__str__()
                    }
        return status

    @property
    def app_allowed_ip_ranges(self):
        allowed_ip_ranges = self.ip_allowlists.values_list(
            "allowed_ip_ranges", flat=True
        ).order_by("pk")
        cleaned_ip_ranges = ",".join(list(set(allowed_ip_ranges))).replace(" ", "")
        return cleaned_ip_ranges

    def env_allowed_ip_ranges(self, env_name):
        related_item_ids = self.appipallowlists.filter(
            deployment_env=env_name
        ).values_list("ip_allowlist_id", flat=True)
        allowed_ip_ranges = (
            IPAllowlist.objects.filter(pk__in=list(related_item_ids))
            .values_list("allowed_ip_ranges", flat=True)
            .order_by("pk")
        )
        cleaned_ip_ranges = ",".join(list(allowed_ip_ranges)).replace(" ", "")
        return cleaned_ip_ranges

    def env_allowed_ip_ranges_names(self, env_name):
        related_item_ids = self.appipallowlists.filter(
            deployment_env=env_name
        ).values_list("ip_allowlist_id", flat=True)
        allowed_ip_ranges = (
            IPAllowlist.objects.filter(pk__in=list(related_item_ids))
            .values_list("name", flat=True)
            .order_by("pk")
        )
        return ", ".join(list(allowed_ip_ranges))

    def env_allow_ip_ranges_ids(self, env_name):
        related_item_ids = self.appipallowlists.filter(
            deployment_env=env_name
        ).values_list("ip_allowlist_id", flat=True)
        return list(related_item_ids)

    def add_customers(self, emails, env_name=None, group_id=None):
        emails = list(filter(None, emails))
        if emails:
            if not group_id:
                group_id = self.get_group_id(env_name)
            try:
                auth0.ExtendedAuth0().add_group_members_by_emails(
                    emails=emails,
                    user_options={"connection": "email"},
                    group_id=group_id,
                )
            except auth0.Auth0Error as e:
                raise AddCustomerError from e

    def delete_customers(self, user_ids, env_name=None, group_id=None):
        try:
            if not group_id:
                group_id = self.get_auth_client(env_name).get("group_id")
            auth0.ExtendedAuth0().groups.delete_group_members(
                user_ids=user_ids,
                group_id=group_id,
            )
        except auth0.Auth0Error as e:
            raise DeleteCustomerError from e

    def delete_customer_by_email(self, email, group_id):
        """
        Attempt to find a customer by email and delete them from the group.
        If the user is not found, or the user does not belong to the given group, raise
        an error.
        """
        auth0_client = auth0.ExtendedAuth0()
        try:
            user = auth0_client.users.get_users_email_search(
                email=email,
                connection="email",
            )[0]
        except auth0.Auth0Error as e:
            raise DeleteCustomerError(str(e)) from e
        except IndexError:
            raise DeleteCustomerError(f"Couldn't find user with email {email}")

        for group in auth0_client.users.get_user_groups(user_id=user["user_id"]):
            if group_id == group["_id"]:
                return self.delete_customers(
                    user_ids=[user["user_id"]], group_id=group_id
                )

        raise DeleteCustomerError(
            f"User {email} cannot be found in this application group"
        )

    @property
    def status(self):
        return "Deployed"

    def delete(self, *args, **kwargs):
        github_api_token = None
        if "github_api_token" in kwargs:
            github_api_token = kwargs.pop("github_api_token")
        cluster.App(self, github_api_token).delete()
        super().delete(*args, **kwargs)

    def auth0_client_name(self, env_name=None):
        """Truncate the length of the name to meet the group_name limit from auth0"""
        allowed_length = settings.AUTH0_CLIENT_NAME_LIMIT - len(env_name or "")
        client_name = self.slug[0:allowed_length-1]
        return settings.AUTH0_CLIENT_NAME_PATTERN.format(
            app_name=client_name, env=env_name)

    def app_url_name(self, env_name):
        format_pattern = settings.APP_URL_NAME_PATTERN.get(env_name.upper())
        if not format_pattern:
            format_pattern = settings.APP_URL_NAME_PATTERN.get(self.DEFAULT_SETTING_KEY_WORD)
        if format_pattern:
            return format_pattern.format(app_name=self.slug, env=env_name)
        else:
            return self.slug

    def get_auth_client(self, env_name):
        env_name = env_name or self.DEFAULT_AUTH_CATEGORY
        return self.auth_settings.get(env_name, {})

    def _init_app_conf(self, env_name):
        if not self.app_conf:
            self.app_conf = {}
        if self.KEY_WORD_FOR_AUTH_SETTINGS not in self.app_conf:
            self.app_conf[self.KEY_WORD_FOR_AUTH_SETTINGS] = {}
        if env_name not in self.app_conf[self.KEY_WORD_FOR_AUTH_SETTINGS]:
            self.app_conf[self.KEY_WORD_FOR_AUTH_SETTINGS][env_name] = {}

    def save_auth_settings(self, env_name, client=None, group=None):
        auth_client_info = {}
        if client:
            auth_client_info.update(dict(client_id=client.get("client_id")))
        if group:
            auth_client_info.update(dict(group_id=group.get("_id")))
        if auth_client_info:
            self._init_app_conf(env_name)
            self.app_conf[self.KEY_WORD_FOR_AUTH_SETTINGS][env_name].update(
                auth_client_info)
            self.save()

    def clear_auth_settings(self, env_name):
        has_auth_related = self.auth_settings.get(env_name)
        if has_auth_related:
            del self.app_conf[self.KEY_WORD_FOR_AUTH_SETTINGS][env_name]
            self.save()

    def get_auth0_group_list(self):
        groups_dict = {}
        for env_name, auth_info in self.auth_settings.items():
            if not auth_info.get('group_id'):
                continue
            groups_dict[auth_info.get('group_id')] = env_name
        return groups_dict

    @property
    def auth_settings(self):
        return (self.app_conf or {}).get(self.KEY_WORD_FOR_AUTH_SETTINGS, {})


class AddCustomerError(Exception):
    pass


class DeleteCustomerError(Exception):
    pass


App.AddCustomerError = AddCustomerError
App.DeleteCustomerError = DeleteCustomerError


# Third-party
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver


@receiver(post_save, sender=App)
def trigger_app_create_related_messages(sender, instance, created, **kwargs):
    if not created:
        return
    tasks.AppCreateRole(instance, instance.current_user).create_task()

    # TODO this could be removed as part of a review of task queue usage
    if instance.deployment_envs:
        tasks.AppCreateAuth(instance, instance.current_user, extra_data=dict(
            deployment_envs=instance.deployment_envs,
            disable_authentication=instance.disable_authentication,
            connections=instance.connections,
            has_ip_ranges=instance.has_ip_ranges,
        )).create_task()


@receiver(post_delete, sender=App)
def remove_app_related_tasks(sender, instance, **kwargs):
    # First-party/Local
    from controlpanel.api.models import Task
    related_app_tasks = Task.objects.filter(entity_class="App", entity_id=instance.id)
    for task in related_app_tasks:
        task.delete()
