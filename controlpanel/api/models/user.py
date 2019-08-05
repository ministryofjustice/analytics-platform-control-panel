from crequest.middleware import CrequestMiddleware
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models

from controlpanel.api import auth0, cluster
from controlpanel.utils import sanitize_dns_label


class User(AbstractUser):
    auth0_id = models.CharField(max_length=128, primary_key=True)
    name = models.CharField(max_length=256, blank=True)
    email_verified = models.BooleanField(default=False)

    REQUIRED_FIELDS = ['email', 'auth0_id']

    class Meta:
        db_table = 'control_panel_api_user'
        ordering = ('username',)

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
        if request.user == self:
            return request.session.get('oidc_id_token')

    @property
    def iam_role_name(self):
        return f"{settings.ENV}_user_{self.username.lower()}"

    @property
    def k8s_namespace(self):
        return f'user-{self.slug}'

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
            User.objects.get(pk=self.pk)
        except User.DoesNotExist:
            cluster.initialize_user(self)

        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        cluster.purge_user(self)
        return super().delete(*args, **kwargs)
