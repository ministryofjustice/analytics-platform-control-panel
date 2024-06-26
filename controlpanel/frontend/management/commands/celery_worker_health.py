# Standard library
import random
from datetime import datetime, timedelta
from pathlib import Path
from sys import exit

# Third-party
from django.conf import settings
from django.core.management.base import BaseCommand

# First-party/Local
from controlpanel.celery import worker_health_check


class Command(BaseCommand):
    help = "Checks if this worker is still running tasks"

    def add_arguments(self, parser):
        parser.add_argument(
            "--stale-after-secs",
            type=int,
            default=120,
            help="For how many seconds the last executed task is considered recent enough for the health check to pass",  # noqa: E501
        )

    def handle(self, *args, **options):
        stale_after_secs = options["stale_after_secs"]
        # send task to randomly chosen queue
        worker_health_check.apply_async(queue=random.choice(settings.PRE_DEFINED_QUEUES))
        # Attempt to read worker health ping file
        # NOTE: This may initially fail depending on timing of health task
        # execution but that's fine as Kubernetes' `failureThreashold`
        # will be more than 1 anyway
        try:
            last_run_at_epoch = Path(settings.WORKER_HEALTH_FILENAME).stat().st_mtime
            last_run_at = datetime.utcfromtimestamp(last_run_at_epoch)
        except FileNotFoundError:
            # Health ping file not found. Health task hasn't run on this worker yet
            self.stderr.write(self.style.ERROR("Health ping file not found"))
            exit(-1)

        self.stdout.write(f"Last run on this worker at: {last_run_at}")

        # check if this worker's health ping file is fresh/recent enough
        if last_run_at < datetime.utcnow() - timedelta(seconds=stale_after_secs):
            self.stderr.write(self.style.ERROR("Health ping file was stale"))
            exit(-1)

        # Health ping file is fresh, success
        self.stdout.write(
            self.style.SUCCESS("Health ping file is fresh. This worker ran health task recently.")
        )
        exit(0)
