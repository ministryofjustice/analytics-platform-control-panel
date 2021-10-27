from crequest.middleware import CrequestMiddleware
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models

from controlpanel.api import auth0, cluster, slack
from controlpanel.utils import sanitize_dns_label


class User(AbstractUser):

    # States in which a user can be in while migrating to the new platform.
    VOID = "v"  # Default value. Not involved in the migration process.
    PENDING = "p"  # User is ready to migrate to the new platform.
    MIGRATING = "m"  # The user has started migration process.
    COMPLETE = "c"  # The migration process has completed for the user.
    REVERTED = "r"  # The user has been reverted to the old platform.

    MIGRATION_STATES = [
        (VOID, "Void - not involved in migration."),
        (PENDING, "Pending - the user is able to migrate."),
        (MIGRATING, "Migrating - migration has started."),
        (COMPLETE, "Complete - migration has completed."),
        (REVERTED, "Reverted - user back on the old platform."),
    ]

    auth0_id = models.CharField(max_length=128, primary_key=True)
    name = models.CharField(max_length=256, blank=True)
    email_verified = models.BooleanField(default=False)
    migration_state = models.CharField(
        help_text="The state of the user's migration to new infrastructure.",
        max_length=1,
        choices=MIGRATION_STATES,
        default=VOID
    )

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
        existing = User.objects.filter(pk=self.pk).first()
        if not existing:
            cluster.User(self).create()

        already_superuser = existing and existing.is_superuser
        if self.is_superuser and not already_superuser:
            request = CrequestMiddleware.get_request()
            slack.notify_superuser_created(
                self.username,
                by_username=request.user.username if request else None,
            )

        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        cluster.User(self).delete()
        return super().delete(*args, **kwargs)

    def authentication_event(self):
        cluster.User(self).on_authenticate()

    @classmethod
    def bulk_migration_update(cls, usernames, new_state):
        """
        Given a list of usernames, will bulk update matching users to the new 
        migration state.
        """
        if usernames:
            users = cls.objects.filter(username__in=usernames)
            for user in users:
                user.migration_state = new_state
            cls.objects.bulk_update(users, ["migration_state", ])
