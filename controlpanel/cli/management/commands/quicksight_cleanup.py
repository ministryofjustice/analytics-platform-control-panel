# Standard library
import csv

# Third-party
import botocore
from django.conf import settings
from django.core.management.base import BaseCommand

# First-party/Local
from controlpanel.api.aws import AWSQuicksight


class Command(BaseCommand):

    READER_ROLES = ["READER"]
    ADMIN_ROLES = [""]

    def add_arguments(self, parser):
        parser.add_argument("file", type=str, help="input: File of usernames", default=None)
        parser.add_argument(
            "--delete",
            required=False,
            action="store_true",
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
            return self.stderr.write(str(e))

        role = response.get("User", {}).get("Role")
        if role not in self.READER_ROLES:
            return self.stdout(f"User {username} is a {role} not a READER, skipping")

        if delete:
            self.quicksight.client.delete_user(**kwargs)

        self.stdout.write(f"User {username} deleted: {delete}")

    def handle(self, *args, **options):
        self.quicksight = AWSQuicksight()
        self.account_id = options["awsaccountid"]
        delete = options["delete"]

        count = 0
        for username in self.usernames_from_file(filename=options["file"]):
            self.delete_user(username=username, delete=delete)
            count += 1

        self.stdout(f"{count} users deleted: {delete}")
