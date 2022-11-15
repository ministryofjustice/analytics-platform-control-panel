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
    ip_allowlists = models.ManyToManyField(IPAllowlist, related_name="apps", related_query_name="app", blank=True)

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

    def get_group_id(self):
        return auth0.ExtendedAuth0().groups.get_group_id(self.slug)

    def customer_paginated(self, page, group_id, per_page=25):
        return (
            auth0.ExtendedAuth0().groups.get_group_members_paginated(
                group_id,
                page=page,
                per_page=per_page
            ) or []
        )

    @property
    def customers(self):
        return (
            auth0.ExtendedAuth0().groups.get_group_members(group_name=self.slug) or []
        )

    @property
    def auth0_connections(self):
        return  auth0.ExtendedAuth0().get_client_enabled_connections(self.slug)

    @property
    def app_aws_secret_name(self):
        return f"{settings.ENV}/apps/{self.slug}/auth"

    @property
    def app_aws_secret_param(self):
        return f"{settings.ENV}/apps/{self.slug}/parameters"

    def get_secret_key(self, name):
        if name == "parameters":
            return self.app_aws_secret_param
        return self.app_aws_secret_name

    def construct_secret_data(self, client):
        """ The assumption is per app per callback url"""
        return {
            "client_id": client["client_id"],
            "client_secret": client["client_secret"],
            "callbacks": client["callbacks"][0] if len(client["callbacks"])>=1 else ""
        }

    def construct_ip_allowlists_string(self):
        app_allowed_ip_ranges = self.ip_allowlists.values_list("allowed_ip_ranges", flat=True).order_by("pk")
        return ", ".join(list(app_allowed_ip_ranges))

    def add_customers(self, emails):
        emails = list(filter(None, emails))
        if emails:
            try:
                auth0.ExtendedAuth0().add_group_members_by_emails(
                    group_name=self.slug,
                    emails=emails,
                    user_options={"connection": "email"},
                )
            except auth0.Auth0Error as e:
                raise AddCustomerError from e

    def delete_customers(self, user_ids):
        try:
            auth0.ExtendedAuth0().groups.delete_group_members(
                group_name=self.slug,
                user_ids=user_ids,
            )
        except auth0.Auth0Error as e:
            raise DeleteCustomerError from e

    @property
    def status(self):
        return "Deployed"

    def save(self, *args, **kwargs):
        is_create = not self.pk

        super().save(*args, **kwargs)

        if is_create:
            cluster.App(self).create_iam_role()

        return self

    def delete(self, *args, **kwargs):
        cluster.App(self).delete()
        auth0.ExtendedAuth0().clear_up_app(app_name=self.slug, group_name=self.slug)

        super().delete(*args, **kwargs)


class AddCustomerError(Exception):
    pass


class DeleteCustomerError(Exception):
    pass


App.AddCustomerError = AddCustomerError
App.DeleteCustomerError = DeleteCustomerError
