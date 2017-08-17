from django.contrib.auth.models import AbstractUser
from django.db import models
from django_extensions.db.fields import AutoSlugField, CreationDateTimeField


class User(AbstractUser):
    class Meta:
        ordering = ('username',)


class App(models.Model):
    created = CreationDateTimeField()
    name = models.CharField(max_length=100, blank=False)
    slug = AutoSlugField(populate_from='name')
    repo_url = models.URLField(max_length=512, blank=True, default='')

    class Meta:
        ordering = ('name',)
