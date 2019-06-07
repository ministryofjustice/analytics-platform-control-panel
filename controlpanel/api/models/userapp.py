from django.db import models
from django_extensions.db.models import TimeStampedModel


class UserApp(TimeStampedModel):
    user = models.ForeignKey(
        "User", on_delete=models.CASCADE, related_name='userapps')
    app = models.ForeignKey(
        "App", on_delete=models.CASCADE, related_name='userapps')
    is_admin = models.BooleanField(default=False)

    class Meta:
        db_table = "control_panel_api_userapp"
        unique_together = (
            ('app', 'user'),
        )
        ordering = ('id',)
