from django.contrib.auth.models import AbstractUser
from django.db import models
from django_extensions.db.fields import AutoSlugField
from django_extensions.db.models import TimeStampedModel

from control_panel_api import services, validators


class User(AbstractUser):
    name = models.CharField(max_length=256, blank=True)

    teams = models.ManyToManyField('Team', through='TeamMembership')

    class Meta:
        ordering = ('username',)

    def get_full_name(self):
        return self.name

    def get_short_name(self):
        return self.name


class App(TimeStampedModel):
    name = models.CharField(max_length=100, blank=False)
    slug = AutoSlugField(populate_from='name', slugify_function=services.app_slug)
    repo_url = models.URLField(max_length=512, blank=True, default='')

    class Meta:
        ordering = ('name',)


class S3Bucket(TimeStampedModel):
    name = models.CharField(unique=True, max_length=63, validators=[
        validators.validate_env_prefix,
        validators.validate_s3_bucket_length,
        validators.validate_s3_bucket_labels,
    ])

    class Meta:
        ordering = ('name',)

    @property
    def arn(self):
        return services.bucket_arn(self.name)


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


class AppS3Bucket(TimeStampedModel):
    """
    An app (potentially) has access to several S3 buckets.

    We have two access levels, "readonly" (default) and "readwrite".
    """

    READONLY = 'readonly'
    READWRITE = 'readwrite'

    ACCESS_LEVELS = (
        (READONLY, "Read-only"),
        (READWRITE, "Read-write"),
    )

    app = models.ForeignKey(
        App, related_name='apps3buckets', on_delete=models.CASCADE)
    s3bucket = models.ForeignKey(
        S3Bucket, related_name='apps3buckets', on_delete=models.CASCADE)
    access_level = models.CharField(
        max_length=9, choices=ACCESS_LEVELS, default=READONLY)

    class Meta:
        # one record per app/s3bucket
        unique_together = ('app', 's3bucket')
