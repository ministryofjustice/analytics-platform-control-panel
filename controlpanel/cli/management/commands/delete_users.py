# Standard library
import csv
import os

# Third-party
from django.core.management.base import BaseCommand

# First-party/Local
from controlpanel.api.models import User


class Command(BaseCommand):
    help = "Delete users from the database based on a file of usernames (supports .txt and .csv)"

    def add_arguments(self, parser):
        parser.add_argument(
            "filepath",
            type=str,
            help="Path to the file containing usernames (.txt with one per line, or .csv)",
        )
        parser.add_argument(
            "--column",
            type=str,
            default="username",
            help="Column name containing usernames (for CSV files, default: 'username')",
        )

    def _read_usernames(self, filepath: str, column: str) -> list[str]:
        """Read usernames from a text or CSV file."""
        ext = os.path.splitext(filepath)[1].lower()

        if ext == ".txt":
            with open(filepath) as f:
                return [line.strip() for line in f if line.strip()]

        if ext == ".csv":
            usernames = []
            with open(filepath, newline="") as f:
                reader = csv.DictReader(f)
                if column not in reader.fieldnames:
                    raise ValueError(
                        f"Column '{column}' not found in CSV. Available columns: {reader.fieldnames}"  # noqa
                    )

                for row in reader:
                    username = row[column].strip()
                    if username:
                        usernames.append(username)
            return usernames

        raise ValueError("Unsupported file type. Please provide a .txt or .csv file.")

    def handle(self, *args, **options):
        filepath = options["filepath"]
        column = options["column"]

        if not os.path.exists(filepath):
            self.stderr.write(self.style.ERROR(f"File not found: {filepath}"))
            return

        try:
            usernames = self._read_usernames(filepath, column)
        except ValueError as e:
            self.stderr.write(self.style.ERROR(str(e)))
            return

        for username in usernames:
            try:
                user = User.objects.get(username=username)
                user.delete()
                self.stdout.write(self.style.SUCCESS(f"Deleted user: {username}"))
            except User.DoesNotExist:
                self.stdout.write(self.style.WARNING(f"User not found: {username}"))
