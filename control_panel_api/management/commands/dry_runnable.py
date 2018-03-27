from django.core.management.base import BaseCommand


class DryRunnable(BaseCommand):
    """
    Add --dry-run flat to command. User will expect command to not
    have side effects.

    NOTE: The input will be available in `options['dry_run']`, you
    will have to add the logic to not have side effects in your command.
    """

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            dest='dry_run',
            help="Run command without side effects",
            default=False,
            action='store_true',
        )
