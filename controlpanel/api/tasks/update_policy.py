# Third-party
import structlog
from celery import shared_task
from django.core.management import call_command

log = structlog.getLogger(__name__)


@shared_task(acks_on_failure_or_timeout=False)
def update_policy(policy_name, attach=True):
    """
    This will add/remove a policy for all users
    """
    call_command("update_policy_for_all_users", "--policy-name", policy_name, "--attach", attach)
