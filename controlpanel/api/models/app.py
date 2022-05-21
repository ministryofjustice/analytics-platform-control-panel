from django.db import models
from django_extensions.db.fields import AutoSlugField
from django_extensions.db.models import TimeStampedModel

from controlpanel.api import auth0, cluster, elasticsearch
from controlpanel.utils import (
    github_repository_name,
    s3_slugify,
    webapp_release_name,
)


class App(TimeStampedModel):
    name = models.CharField(max_length=100, blank=False)
    description = models.TextField(blank=True)
    slug = AutoSlugField(populate_from='_repo_name', slugify_function=s3_slugify)
    repo_url = models.URLField(max_length=512, blank=False, unique=True)
    created_by = models.ForeignKey("User", on_delete=models.SET_NULL, null=True)

    class Meta:
        db_table = "control_panel_api_app"
        ordering = ('name',)

    def __repr__(self):
        return f'<App: {self.slug}>'

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

    @property
    def customers(self):
        return auth0.ExtendedAuth0().groups.get_group_members(group_name=self.slug) or []

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
