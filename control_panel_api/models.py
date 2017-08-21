from django.contrib.auth.models import AbstractUser
from django.db import models
from django_extensions.db.fields import AutoSlugField, CreationDateTimeField


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
