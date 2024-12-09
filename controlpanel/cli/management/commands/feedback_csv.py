# Standard library
import csv
from datetime import datetime, timedelta
from io import StringIO

# Third-party
from django.conf import settings
from django.core.management.base import BaseCommand

# First-party/Local
from controlpanel.api.aws import AWSBucket
from controlpanel.api.models import Feedback


class Command(BaseCommand):
    help = "Writes a csv file with the feedback data to an S3 Bucket"
    csv_headings = ["Satisfaction Rating", "Suggestions", "Date Added"]

    def add_arguments(self, parser):
        parser.add_argument(
            "--weeks",
            "-w",
            type=int,
            default=2,
            help="Get feedback over an x week period from today's date",
        )
        parser.add_argument("--all", "-a", action="store_true", help="Get all feedback received")

    def handle(self, *args, **options):
        today = datetime.today()

        if options["all"]:
            feedback_items = Feedback.objects.all()
        else:
            self.stdout.write(f"weeks: {options['weeks']}")
            timeframe = today - timedelta(weeks=options["weeks"])
            feedback_items = Feedback.objects.filter(date_added__gte=timeframe)

        if not feedback_items:
            self.stdout.write(f"No feedback found for the past {options['weeks']} weeks")
            return

        filename = f"feedback_{today}.csv"
        csv_buffer = StringIO()
        writer = csv.writer(csv_buffer, delimiter=",", quotechar="|", quoting=csv.QUOTE_MINIMAL)
        writer.writerow(self.csv_headings)
        for feedback in feedback_items:
            row = [
                feedback.get_satisfaction_rating_display(),
                feedback.suggestions,
                feedback.date_added.date(),
            ]
            writer.writerow(row)

        try:
            csv_value = csv_buffer.getvalue()
            bucket = AWSBucket()

            if not bucket.exists(settings.FEEDBACK_BUCKET_NAME):
                bucket.create(settings.FEEDBACK_BUCKET_NAME)

            bucket.write_to_bucket(settings.FEEDBACK_BUCKET_NAME, filename, csv_value)
            self.stdout.write(f"Feedback data written to {settings.FEEDBACK_BUCKET_NAME}")
        except Exception as e:
            self.stdout.write(f"Failed to write to S3 bucket: {e}")
