from django.conf import settings
from django.db import models
from django_extensions.db.fields import AutoSlugField
from django_extensions.db.models import TimeStampedModel

from controlpanel.api import auth0, cluster
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

    @property
    def admins(self):
        return [ua.user for ua in self.userapps.filter(is_admin=True)]

    @property
    def iam_role_name(self):
        return f"{settings.ENV}_app_{self.slug}"

    @property
    def _repo_name(self):
        return github_repository_name(self.repo_url)

    @property
    def release_name(self):
        return webapp_release_name(self._repo_name)

    @property
    def customers(self):
        return auth0.AuthorizationAPI().get_group_members(group_name=self.slug) or []

    def add_customers(self, emails):
        emails = list(filter(None, emails))
        if emails:
            auth0.AuthorizationAPI().add_group_members(
                group_name=self.slug,
                emails=emails,
                user_options={"connection": "email"},
            )

    def delete_customers(self, user_ids):
        auth0.AuthorizationAPI().delete_group_members(
            group_name=self.slug, user_ids=user_ids
        )

    @property
    def status(self):
        return "Deployed"

    def save(self, *args, **kwargs):
        is_create = not self.pk

        super().save(*args, **kwargs)

        if is_create:
            cluster.create_app_role(self.iam_role_name)

        return self

    def delete(self, *args, **kwargs):
        cluster.delete_app_role(self.iam_role_name)
        super().delete(*args, **kwargs)
