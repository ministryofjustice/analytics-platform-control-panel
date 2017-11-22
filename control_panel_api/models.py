import re

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.template.defaultfilters import slugify
from django_extensions.db.fields import AutoSlugField
from django_extensions.db.models import TimeStampedModel

from control_panel_api import services, validators
from control_panel_api.helm import helm


class User(AbstractUser):
    auth0_id = models.CharField(max_length=128, primary_key=True)
    name = models.CharField(max_length=256, blank=True)

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

    def aws_create_role(self):
        services.create_role(self.iam_role_name, add_saml_statement=True)

    def aws_delete_role(self):
        services.delete_role(self.iam_role_name)

    def helm_create(self):
        helm.init_user(self.username, self.email, self.get_full_name())
        helm.config_user(self.username)


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


class S3Bucket(TimeStampedModel):
    name = models.CharField(unique=True, max_length=63, validators=[
        validators.validate_env_prefix,
        validators.validate_s3_bucket_length,
        validators.validate_s3_bucket_labels,
    ])
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    class Meta:
        ordering = ('name',)

    @property
    def arn(self):
        return f"arn:aws:s3:::{self.name}"

    def aws_create(self):
        services.create_bucket(self.name)
        services.create_bucket_policies(self.name, self.arn)

    def aws_delete(self):
        """Note we do not destroy the actual data, just the policies"""
        services.delete_bucket_policies(self.name)

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
        services.attach_bucket_access_to_role(
            self.s3bucket.name,
            self.has_readwrite_access(),
            self.aws_role_name(),
        )

    def aws_delete(self):
        services.detach_bucket_access_from_role(
            self.s3bucket.name,
            self.has_readwrite_access(),
            self.aws_role_name(),
        )

    def aws_update(self):
        services.update_bucket_access(
            self.s3bucket.name,
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
