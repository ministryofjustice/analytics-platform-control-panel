from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Meta:
        ordering = ('username',)


class Project(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    name = models.CharField(max_length=100, blank=False)
    slug = models.CharField(max_length=100, blank=False)
    repository = models.CharField(max_length=255, blank=True, default='')

    class Meta:
        ordering = ('name',)
