# Standard library
import json
import uuid

# Third-party
from django.conf import settings
from django.db import models
from django_extensions.db.fields import AutoSlugField
from django_extensions.db.models import TimeStampedModel

# First-party/Local
from controlpanel.api import auth0, cluster, elasticsearch
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

    DEFAULT_KEY_WORD = "DEFAULT"

    class Meta:
        db_table = "control_panel_api_app"
        ordering = ("name",)

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

    def get_logs(self, num_hours=None):
        return elasticsearch.app_logs(self, num_hours=num_hours)

    def get_group_id(self, env_name):
        return auth0.ExtendedAuth0().groups.get_group_id(
            self.auth0_client_name(env_name)
        )

    def customers(self, env_name=None):
        return (
            auth0.ExtendedAuth0().groups.get_group_members(
                group_name=self.auth0_client_name(env_name)
            )
            or []
        )

    def customer_paginated(self, page, group_id, per_page=25):
        return (
            auth0.ExtendedAuth0().groups.get_group_members_paginated(
                group_id, page=page, per_page=per_page
            )
            or []
        )

    def auth0_connections(self, env_name):
        return auth0.ExtendedAuth0().get_client_enabled_connections(
            self.auth0_client_name(env_name)
        )

    @property
    def app_allowed_ip_ranges(self):
        allowed_ip_ranges = self.ip_allowlists.values_list(
            "allowed_ip_ranges", flat=True
        ).order_by("pk")
        return ", ".join(list(set(allowed_ip_ranges)))

    def env_allowed_ip_ranges(self, env_name):
        related_item_ids = self.appipallowlists.filter(
            deployment_env=env_name
        ).values_list("ip_allowlist_id", flat=True)
        allowed_ip_ranges = (
            IPAllowlist.objects.filter(pk__in=list(related_item_ids))
            .values_list("allowed_ip_ranges", flat=True)
            .order_by("pk")
        )
        return ", ".join(list(allowed_ip_ranges))

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
            try:
                auth0.ExtendedAuth0().add_group_members_by_emails(
                    group_name=self.auth0_client_name(env_name),
                    emails=emails,
                    user_options={"connection": "email"},
                    group_id=group_id,
                )
            except auth0.Auth0Error as e:
                raise AddCustomerError from e

    def delete_customers(self, user_ids, env_name=None, group_id=None):
        try:
            auth0.ExtendedAuth0().groups.delete_group_members(
                group_name=self.auth0_client_name(env_name),
                user_ids=user_ids,
                group_id=group_id,
            )
        except auth0.Auth0Error as e:
            raise DeleteCustomerError from e

    def delete_customer_by_email(self, email, group_id=None, env_name=None):
        """
        Attempt to find a customer by email and delete them from the group.
        If the user is not found, or the user does not belong to the given group, raise
        an error.
        """
        group_id = group_id or self.get_group_id(env_name=env_name)
        auth0_client = auth0.ExtendedAuth0()
        try:
            user = auth0_client.users.get_users_email_search(
                email=email,
                connection="email",
            )[0]
        except (auth0.Auth0Error, IndexError) as e:
            raise DeleteCustomerError from e

        for group in auth0_client.users.get_user_groups(user_id=user["user_id"]):
            if group_id == group["_id"]:
                return self.delete_customers(
                    user_ids=[user["user_id"]], group_id=group_id
                )

        raise DeleteCustomerError

    @property
    def status(self):
        return "Deployed"

    def deployment_envs(self, github_token):
        return cluster.App(self, github_token).get_deployment_envs()

    def delete(self, *args, **kwargs):
        github_api_token = None
        if "github_api_token" in kwargs:
            github_api_token = kwargs.pop("github_api_token")
        cluster.App(self, github_api_token).delete()
        super().delete(*args, **kwargs)

    def _get_old_auth0_client_name(self):
        """TODO This function needs to be adjusted once the migration is over"""
        try:
            app_conf = json.loads(self.description)
        except ValueError:
            app_conf = {}
        return app_conf.get('app_name') or self.slug

    def auth0_client_name(self, env_name=None):
        if env_name:
            return settings.AUTH0_CLIENT_NAME_PATTERN.format(
                app_name=self.slug, env=env_name)
        else:
            return self._get_old_auth0_client_name()

    @property
    def migration_info(self):
        # TODO: using app.description for temporary place for storing old app info,
        #  The content of this field should be removed after app migration is completed.
        try:
            return json.loads(self.description).get("migration", {})
        except ValueError:
            return {}

    def app_url_name(self, env_name):
        format_pattern = settings.APP_URL_NAME_PATTERN.get(env_name.upper())
        if not format_pattern:
            format_pattern = settings.APP_URL_NAME_PATTERN.get(self.DEFAULT_KEY_WORD)
        if format_pattern:
            return format_pattern.format(app_name=self.slug, env=env_name)
        else:
            return self.slug


class AddCustomerError(Exception):
    pass


class DeleteCustomerError(Exception):
    pass


App.AddCustomerError = AddCustomerError
App.DeleteCustomerError = DeleteCustomerError
