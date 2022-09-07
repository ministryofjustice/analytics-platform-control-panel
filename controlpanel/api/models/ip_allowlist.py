from django.db import models

from auditlog.models import AuditlogHistoryField
from auditlog.registry import auditlog

class IPAllowlist(models.Model):
    name = models.CharField(max_length=100, blank=False, unique=True)
    description = models.CharField(max_length=100, blank=True)
    contact = models.CharField(max_length=100, blank=True)
    allowed_ip_ranges = models.TextField(blank=False)
    history = AuditlogHistoryField()

auditlog.register(IPAllowlist)
