# Third-party
from crequest.middleware import CrequestMiddleware
from django.contrib.auth.models import AbstractUser
from django.contrib.auth.signals import user_logged_in
from django.db import models
from django.urls import reverse
from django.utils.functional import cached_property

# First-party/Local
from controlpanel.api import auth0, cluster, slack
from controlpanel.api.signals import prometheus_login_event
from controlpanel.utils import sanitize_dns_label

QUICKSIGHT_EMBED_AUTHOR_PERMISSION = "quicksight_embed_author_access"
QUICKSIGHT_EMBED_READER_PERMISSION = "quicksight_embed_reader_access"


class User(AbstractUser):

    # States in which a user can be in while migrating to the new platform.
    VOID = "v"  # Default value. Not involved in the migration process.
    PENDING = "p"  # User is ready to migrate to the new platform.
    MIGRATING = "m"  # The user has started migration process.
    COMPLETE = "c"  # The migration process has completed for the user.
    REVERTED = "r"  # The user has been reverted to the old platform.

    MIGRATION_STATES = [
        (VOID, "Void"),
        (PENDING, "Pending"),
        (MIGRATING, "Migrating"),
        (COMPLETE, "Complete"),
        (REVERTED, "Reverted"),
    ]

    auth0_id = models.CharField(max_length=128, primary_key=True)
    name = models.CharField(max_length=256, blank=True)
    email_verified = models.BooleanField(default=False)
    migration_state = models.CharField(
        help_text="The state of the user's migration to new infrastructure.",
        max_length=1,
        choices=MIGRATION_STATES,
        default=VOID,
    )
    is_bedrock_enabled = models.BooleanField(default=False)
    is_database_admin = models.BooleanField(default=False)
    justice_email = models.EmailField(blank=True, null=True, unique=True)
    azure_oid = models.CharField(blank=True, null=True, unique=True)

    REQUIRED_FIELDS = ["email", "auth0_id"]

    class Meta:
        db_table = "control_panel_api_user"
        ordering = ("username",)
        permissions = [
            (QUICKSIGHT_EMBED_AUTHOR_PERMISSION, "Can access embedded QuickSight as an author"),
            (QUICKSIGHT_EMBED_READER_PERMISSION, "Can access embedded QuickSight as a reader"),
        ]

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
                "request not found: have you called get_id_token() in a " "background worker?"
            )

        if request.user == self:
            return request.session.get("oidc_id_token")

    @property
    def iam_role_name(self):
        return cluster.User(self).iam_role_name

    @property
    def k8s_namespace(self):
        return cluster.User(self).k8s_namespace

    @property
    def github_api_token(self):
        if not hasattr(self, "_github_api_token"):
            self._github_api_token = None
        if not getattr(self, "_github_api_token", None):
            auth0_user = auth0.ExtendedAuth0().users.get(self.auth0_id)
            for identity in auth0_user["identities"]:
                if identity["provider"] == "github":
                    self._github_api_token = identity.get("access_token")
        return self._github_api_token

    @github_api_token.setter
    def github_api_token(self, value):
        self._github_api_token = value

    @property
    def slug(self):
        return sanitize_dns_label(self.username)

    @property
    def is_quicksight_enabled(self):
        return cluster.User(self).has_policy_attached(
            policy_name=cluster.User.QUICKSIGHT_POLICY_NAME
        )

    @cached_property
    def show_webapp_data_link(self):
        """
        Check if the user already has an app bucket, or if the user is an admin of an
        app
        """
        if self.is_superuser:
            return True

        if (
            self.users3buckets.filter(s3bucket__is_deleted=False)
            .exclude(s3bucket__is_data_warehouse=True)
            .exists()
        ):
            return True

        return self.userapps.filter(is_admin=True).exists()

    @property
    def is_iam_user(self):
        """
        Determine if the user was created via the github connection. We can use this to limit what
        actions non-github users do within the AP.
        This has been added specifically to allow CICA users to authenticate with EntraID in order
        to access QuickSight in the AP. This is a temporary change, that should be removed once auth
        with Entra is fully implemented.
        """
        return self.auth0_id.startswith("github|")

    def is_app_admin(self, app_id):
        return (
            self.userapps.filter(
                app_id=app_id,
                is_admin=True,
            ).count()
            != 0
        )

    def is_dashboard_admin(self, dashboard_id):
        return self.dashboards.filter(
            id=dashboard_id,
        ).exists()

    def is_bucket_admin(self, bucket_id):
        return (
            self.users3buckets.filter(
                s3bucket__id=bucket_id,
                is_admin=True,
            ).count()
            != 0
        )

    def is_quicksight_user(self):
        return self.has_perm("api.quicksight_embed_author_access") or self.has_perm(
            "api.quicksight_embed_reader_access"
        )

    def reset_mfa(self):
        auth0.ExtendedAuth0().users.reset_mfa(self.auth0_id)

    def set_bedrock_access(self):
        if self.is_iam_user:
            return cluster.User(self).update_policy_attachment(
                policy=cluster.BEDROCK_POLICY_NAME,
                attach=self.is_bedrock_enabled,
            )

    def set_quicksight_access(self, enable):
        if self.is_iam_user:
            return cluster.User(self).update_policy_attachment(
                policy=cluster.User.QUICKSIGHT_POLICY_NAME,
                attach=enable,
            )

    def save(self, *args, **kwargs):
        existing = User.objects.filter(pk=self.pk).first()
        if not existing and self.is_iam_user:
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
        auth0.ExtendedAuth0().clear_up_user(user_id=self.auth0_id)
        return super().delete(*args, **kwargs)

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
            cls.objects.bulk_update(
                users,
                [
                    "migration_state",
                ],
            )

    def get_absolute_url(self):
        return reverse("manage-user", kwargs={"pk": self.pk})


user_logged_in.connect(prometheus_login_event)
