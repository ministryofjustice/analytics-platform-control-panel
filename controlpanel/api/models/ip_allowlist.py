from django.db import models

from simple_history.models import HistoricalRecords

class IPAllowlist(models.Model):
    name = models.CharField(max_length=100, blank=False, unique=True)
    description = models.CharField(max_length=100, blank=True)
    contact = models.CharField(max_length=100, blank=True)
    allowed_ip_ranges = models.TextField(blank=False)
    history = HistoricalRecords()
