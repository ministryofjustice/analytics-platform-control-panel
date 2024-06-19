# Standard library
import csv

# Third-party
import botocore
from django.conf import settings
from django.core.management.base import BaseCommand

# First-party/Local
from controlpanel.api import aws


class Command(BaseCommand):
    """
    This command will delete users from Quicksight based on the csv file provided.
    """

    READER_ROLES = ["READER"]

    def add_arguments(self, parser):
        parser.add_argument(
            "file", type=str, help="input: csv of Quicksight usernames", default=None
        )
        parser.add_argument(
            "--delete",
            required=False,
            action="store_true",
            help="Deletes users when provided, otherwise will be a dry run.",
        )
        parser.add_argument(
            "-a", "--awsaccountid", required=False, type=str, default=settings.AWS_DATA_ACCOUNT_ID
        )

    def usernames_from_file(self, filename):
        with open(filename) as csv_file:
            csv_reader = csv.reader(csv_file, delimiter=",")
            for row in csv_reader:
                yield row[0]

    def delete_user(self, username, delete=False):
        # check the user is a reader
        kwargs = {"UserName": username, "AwsAccountId": self.account_id, "Namespace": "default"}
        try:
            response = self.quicksight.client.describe_user(**kwargs)
        except botocore.exceptions.ClientError as e:
            self.stderr.write(str(e))
            return False

        role = response.get("User", {}).get("Role")
        if role not in self.READER_ROLES:
            self.stdout.write(f"User {username} is a {role} not a READER, skipping")
            return False

        if delete:
            self.quicksight.client.delete_user(**kwargs)

        self.stdout.write(f"User {username} deleted: {delete}")
        return True

    def handle(self, *args, **options):
        self.quicksight = aws.AWSQuicksight()
        self.account_id = options["awsaccountid"]
        delete = options["delete"]

        count = 0
        for username in self.usernames_from_file(filename=options["file"]):
            deleted = self.delete_user(username=username, delete=delete)
            if deleted:
                count += 1

        self.stdout.write(f"{count} users deleted: {delete}")
