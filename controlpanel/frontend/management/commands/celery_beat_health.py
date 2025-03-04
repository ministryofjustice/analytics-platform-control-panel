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
    help = "Checks if celery beat is ready by checking for heath file"

    def handle(self, *args, **options):

        if not Path(settings.WORKER_HEALTH_FILENAME).is_file():
            self.stderr.write(self.style.ERROR("Health file not found"))
            exit(-1)

        self.stdout.write(self.style.SUCCESS("Health file found"))
        exit(0)
