from django.db import models
from django_extensions.db.models import TimeStampedModel


class TeamMembership(TimeStampedModel):
    """
    User's membership to a team. A user is member of a team with a
    given role, e.g. user_1 is maintainer (role) in team_1
    """

    team = models.ForeignKey("Team", on_delete=models.CASCADE)
    role = models.ForeignKey("Role", on_delete=models.CASCADE)
    user = models.ForeignKey("User", on_delete=models.CASCADE)

    class Meta:
        db_table = "control_panel_api_teammembership"
        unique_together = (
            # a user can be in a team only once and with exactly one role
            ('user', 'team'),
        )
