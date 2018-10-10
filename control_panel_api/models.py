import re

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models.signals import post_delete
from django.template.defaultfilters import slugify
from django_extensions.db.fields import AutoSlugField
from django_extensions.db.models import TimeStampedModel

from control_panel_api import services, validators
from control_panel_api.auth0 import Auth0
from control_panel_api.helm import helm
from control_panel_api.utils import sanitize_dns_label


logger = __import__('logging').getLogger(__name__)


class User(AbstractUser):
    auth0_id = models.CharField(max_length=128, primary_key=True)
    name = models.CharField(max_length=256, blank=True)
    email_verified = models.BooleanField(default=False)

    teams = models.ManyToManyField('Team', through='TeamMembership')

    REQUIRED_FIELDS = ['email', 'auth0_id']

    class Meta:
        ordering = ('username',)

    def get_full_name(self):
        return self.name

    def get_short_name(self):
        return self.name

    @property
    def iam_role_name(self):
        return f"{settings.ENV}_user_{self.username.lower()}"

    @property
    def k8s_namespace(self):
        return sanitize_dns_label(f'user-{self.username}')

    def aws_create_role(self):
        logger.info(f'aws_create_role "{self.iam_role_name}"')
        services.create_role(
            self.iam_role_name, add_saml_statement=True,
            add_oidc_statement=True, oidc_sub=self.auth0_id)
        services.grant_read_inline_policies(self.iam_role_name)

    def aws_delete_role(self):
        services.delete_role(self.iam_role_name)

    def helm_create(self):
        logger.info(f'helm_create "{self.username}"')
        helm.init_user(self.username, self.email, self.get_full_name())
        helm.config_user(self.username)

    def helm_delete(self):
        logger.info(f'helm_delete "{self.username}""')
        helm.uninstall_user_charts(self.username)
        helm.uninstall_init_user_chart(self.username)


class App(TimeStampedModel):
    def _slugify(name):
        """Create a slug using standard django slugify but we override with
        extra replacement so it's valid for s3"""
        return re.sub(r'_+', '-', slugify(name))

    name = models.CharField(max_length=100, blank=False)
    description = models.TextField(blank=True)
    slug = AutoSlugField(populate_from='_repo_name', slugify_function=_slugify)
    repo_url = models.URLField(max_length=512, blank=False, unique=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    class Meta:
        ordering = ('name',)

    @property
    def iam_role_name(self):
        return f"{settings.ENV}_app_{self.slug}"

    def aws_create_role(self):
        services.create_role(self.iam_role_name)

    def aws_delete_role(self):
        services.delete_role(self.iam_role_name)

    @property
    def _repo_name(self):
        """Returns the repo name

        The name is the part after the last slash in the URL, without
        the '.git' (if present).

        Examples:

        "https://github.com/org/a_repo_name" => "a_repo_name"
        "git@github.com:org/repo_2.git" => "repo_2"
        """
        repo_name = self.repo_url

        if repo_name.endswith('/'):
            repo_name = repo_name[:-1]

        if repo_name.endswith('.git'):
            repo_name = repo_name[:-4]

        return repo_name.rsplit('/', 1)[1]

    def get_customers(self):
        return Auth0().get_group_members(group_name=self.slug)

    def add_customers(self, emails):
        Auth0().add_group_members(
            group_name=self.slug,
            emails=emails,
            user_options={'connection': 'email'})

    def delete_customers(self, user_ids):
        Auth0().delete_group_members(
            group_name=self.slug,
            user_ids=user_ids)


class UserApp(TimeStampedModel):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='userapps')
    app = models.ForeignKey(
        App, on_delete=models.CASCADE, related_name='userapps')
    is_admin = models.BooleanField(default=False)

    class Meta:
        unique_together = (
            ('app', 'user'),
        )
        ordering = ('id',)


class S3BucketQuerySet(models.QuerySet):
    def accessible_by(self, user):
        return self.filter(
            users3buckets__user=user,
        )

    def administered_by(self, user):
        return self.filter(
            users3buckets__user=user,
            users3buckets__is_admin=True,
        )


class S3Bucket(TimeStampedModel):
    name = models.CharField(unique=True, max_length=63, validators=[
        validators.validate_env_prefix,
        validators.validate_s3_bucket_length,
        validators.validate_s3_bucket_labels,
    ])
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    is_data_warehouse = models.BooleanField(default=False)
    location_url = models.CharField(max_length=128, null=True)

    objects = S3BucketQuerySet.as_manager()

    class Meta:
        ordering = ('name',)

    @property
    def arn(self):
        return f"arn:aws:s3:::{self.name}"

    def aws_create(self):
        result = services.create_bucket(self.name, self.is_data_warehouse)

        if result:
            self.location_url = result['Location']

    def create_users3bucket(self, user):
        users3bucket = UserS3Bucket.objects.create(
            user=user,
            s3bucket=self,
            is_admin=True,
            access_level=UserS3Bucket.READWRITE,
        )
        users3bucket.aws_create()


class Role(TimeStampedModel):
    name = models.CharField(max_length=256, blank=False, unique=True)
    code = models.CharField(max_length=256, blank=False, unique=True)

    class Meta:
        ordering = ('name',)


class Team(TimeStampedModel):
    name = models.CharField(max_length=256, blank=False)
    slug = AutoSlugField(populate_from='name')

    users = models.ManyToManyField('User', through='TeamMembership')

    class Meta:
        ordering = ('name',)

    def users_with_role(self, role_code):
        """
        Returns the users (queryset) with the given `role_code `in the team
        """

        return self.users.filter(teammembership__role__code=role_code)


class TeamMembership(TimeStampedModel):
    """
    User's membership to a team. A user is member of a team with a
    given role, e.g. user_1 is maintainer (role) in team_1
    """

    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    role = models.ForeignKey(Role, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    class Meta:
        unique_together = (
            # a user can be in a team only once and with exactly one role
            ('user', 'team'),
        )


class AccessToS3Bucket(TimeStampedModel):
    """
    Abstract model to model access to S3 buckets

    These models will be associated with an s3bucket and have
    an access level (`readonly` or `readwrite`)
    """

    READONLY = 'readonly'
    READWRITE = 'readwrite'

    ACCESS_LEVELS = (
        (READONLY, "Read-only"),
        (READWRITE, "Read-write"),
    )

    s3bucket = models.ForeignKey(
        S3Bucket, related_name='%(class)ss', on_delete=models.CASCADE)
    access_level = models.CharField(
        max_length=9, choices=ACCESS_LEVELS, default=READONLY)

    class Meta:
        abstract = True

    def has_readwrite_access(self):
        return self.access_level == self.READWRITE

    def aws_role_name(self):
        raise NotImplementedError

    def aws_create(self):
        self.aws_update()

    def aws_update(self):
        services.grant_bucket_access(
            self.s3bucket.arn,
            self.has_readwrite_access(),
            self.aws_role_name(),
        )


class AppS3Bucket(AccessToS3Bucket):
    """
    An app (potentially) has access to several S3 buckets.

    We have two access levels, "readonly" (default) and "readwrite".
    """

    app = models.ForeignKey(
        App, related_name='apps3buckets', on_delete=models.CASCADE)

    class Meta:
        # one record per app/s3bucket
        unique_together = ('app', 's3bucket')
        ordering = ('id',)

    def aws_role_name(self):
        return self.app.iam_role_name


class UserS3Bucket(AccessToS3Bucket):
    """
    A user can have access to several S3 buckets.

    We have two access levels, "readonly" (default) and "readwrite".
    The `is_admin` field determine if the user has admin privileges on the
    S3 bucket
    """

    user = models.ForeignKey(
        User, related_name='users3buckets', on_delete=models.CASCADE)
    is_admin = models.BooleanField(default=False)

    class Meta:
        # one record per user/s3bucket
        unique_together = ('user', 's3bucket')
        ordering = ('id',)

    def aws_role_name(self):
        return self.user.iam_role_name

    def user_is_admin(self, user):
        return self.user == user and self.is_admin


def _access_to_bucket_deleted(sender, **kwargs):
    access_to_bucket = kwargs['instance']

    services.revoke_bucket_access(
        access_to_bucket.s3bucket.arn,
        access_to_bucket.aws_role_name(),
    )


post_delete.connect(
    _access_to_bucket_deleted,
    sender=AppS3Bucket,
    dispatch_uid='control_panel_api.models._access_to_bucket_deleted',
)
post_delete.connect(
    _access_to_bucket_deleted,
    sender=UserS3Bucket,
    dispatch_uid='control_panel_api.models._access_to_bucket_deleted',
)
