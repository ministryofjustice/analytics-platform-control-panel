from crequest.middleware import CrequestMiddleware
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models

from controlpanel.api import auth0, cluster, slack
from controlpanel.utils import sanitize_dns_label


class User(AbstractUser):
    auth0_id = models.CharField(max_length=128, primary_key=True)
    name = models.CharField(max_length=256, blank=True)
    email_verified = models.BooleanField(default=False)

    REQUIRED_FIELDS = ['email', 'auth0_id']

    class Meta:
        db_table = 'control_panel_api_user'
        ordering = ('username',)

    def __repr__(self):
        return f"<User: {self.username} ({self.auth0_id})>"

    def get_full_name(self):
        return self.name

    @property
    def id(self):
        return self.pk

    def get_id_token(self):
        """
        Retrieve the user's Id token if they are the logged in user
        """
        request = CrequestMiddleware.get_request()
        if not request:
            raise Exception(
                "request not found: have you called get_id_token() in a "
                "background worker?"
            )

        if request.user == self:
            return request.session.get('oidc_id_token')

    @property
    def iam_role_name(self):
        return cluster.User(self).iam_role_name

    @property
    def k8s_namespace(self):
        return cluster.User(self).k8s_namespace

    @property
    def github_api_token(self):
        if not getattr(self, '_github_api_token', None):
            auth0_user = auth0.ManagementAPI().get_user(self.auth0_id)
            for identity in auth0_user["identities"]:
                if identity['provider'] == 'github':
                    self._github_api_token = identity.get('access_token')
        return self._github_api_token

    @github_api_token.setter
    def github_api_token(self, value):
        self._github_api_token = value

    @property
    def slug(self):
        return sanitize_dns_label(self.username)

    def is_app_admin(self, app_id):
        return self.userapps.filter(
            app_id=app_id,
            is_admin=True,
        ).count() != 0

    def is_bucket_admin(self, bucket_id):
        return self.users3buckets.filter(
            s3bucket__id=bucket_id,
            is_admin=True,
        ).count() != 0

    def reset_mfa(self):
        auth0.ManagementAPI().reset_mfa(self.auth0_id)

    def save(self, *args, **kwargs):
        try:
            existing = User.objects.get(pk=self.pk)

        except User.DoesNotExist:
            cluster.User(self).create()
            if self.is_superuser:
                slack.notify_team(
                    f"`{self.username}` was created as a superuser"
                )

        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        cluster.User(self).delete()
        return super().delete(*args, **kwargs)
