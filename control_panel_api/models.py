from django.contrib.auth.models import AbstractUser
from django.db import models
from django_extensions.db.fields import AutoSlugField, CreationDateTimeField, ModificationDateTimeField


class User(AbstractUser):
    name = models.CharField(max_length=256, blank=True)

    class Meta:
        ordering = ('username',)

    def get_full_name(self):
        return self.name

    def get_short_name(self):
        return self.name


class App(models.Model):
    created = CreationDateTimeField()
    name = models.CharField(max_length=100, blank=False)
    slug = AutoSlugField(populate_from='name')
    repo_url = models.URLField(max_length=512, blank=True, default='')

    class Meta:
        ordering = ('name',)


class Role(models.Model):
    created = CreationDateTimeField()
    code = models.CharField(max_length=256, blank=False, unique=True)

    class Meta:
        ordering = ('code',)


class Team(models.Model):
    created = CreationDateTimeField()
    name = models.CharField(max_length=256, blank=False)
    slug = AutoSlugField(populate_from='name')

    class Meta:
        ordering = ('name',)


class TeamMembership(models.Model):
    """
    User's membership to a team. A user is member of a team with a
    given role, e.g. user_1 is maintainer (role) in team_1
    """

    created = CreationDateTimeField()
    modified = ModificationDateTimeField()

    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    role = models.ForeignKey(Role, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    class Meta:
        unique_together = (
            # a user can be in a team only once and with exactly one role
            ('user', 'team', 'role'),
            ('user', 'team'),
        )
