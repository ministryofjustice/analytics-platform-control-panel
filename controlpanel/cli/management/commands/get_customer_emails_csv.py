# Standard library
import csv
from datetime import datetime

# Third-party
from django.core.management import BaseCommand

# First-party/Local
from controlpanel.api import auth0


class Command(BaseCommand):
    help = "Writes a CSV with all customer emails for an auth0 group"

    def add_arguments(self, parser):
        parser.add_argument(
            "group_name", type=str, help="input: The auth0 group name to get customers emails for"
        )

    def handle(self, *args, **options):
        group_name = options["group_name"]
        auth_instance = auth0.ExtendedAuth0()
        group_id = auth_instance.groups.get_group_id(group_name)
        timestamp = datetime.now().strftime("%d-%m-%Y_%H%M")
        with open(f"{group_name}_customers_{timestamp}.csv", "w") as f:
            writer = csv.writer(f)
            writer.writerow(["Email"])
            for customer in auth_instance.groups.get_group_members(group_id):
                writer.writerow([customer["email"]])
