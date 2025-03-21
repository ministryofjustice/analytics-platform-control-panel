# Third-party
from django.db import models


class JusticeDomain(models.Model):
    """
    Represents a valid Justice email domain. This is used to validate users that can access
    Quicksight.
    """

    domain = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return self.domain
