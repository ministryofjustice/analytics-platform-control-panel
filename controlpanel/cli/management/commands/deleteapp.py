from django.core.management.base import BaseCommand, CommandError
from django.core.validators import validate_slug
from django.core.exceptions import ValidationError

from controlpanel.api.models import App

class Command(BaseCommand):
    help = "Hello from new cli app"

    def add_arguments(self, parser):
        parser.add_argument("slug", type=str)

    def handle(self, *args, **options):
        print(options["slug"])
        try:
            validate_slug(options["slug"])
        except ValidationError as e:
            raise CommandError("App name should be a valid slug")

        try:
            app = App.objects.get(slug=options["slug"])
        except App.DoesNotExist:
            raise CommandError("This app does not exist")

        app.delete()
