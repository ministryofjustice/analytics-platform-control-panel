from django.core.management.base import BaseCommand, CommandError
from django.core.validators import validate_slug
from django.core.exceptions import ValidationError

from controlpanel.api.models import App


class Command(BaseCommand):
    help = "Delete an app"

    def add_arguments(self, parser):
        parser.add_argument("slug", type=str, help="Slug of the app to delete")
        parser.add_argument(
            "-y", "--yes", action="store_true", help="Skip confirmation of app deletion"
        )

    def handle(self, *args, **options):
        try:
            validate_slug(options["slug"])
        except ValidationError:
            raise CommandError("App name should be a valid slug")

        try:
            app = App.objects.get(slug=options["slug"])
        except App.DoesNotExist:
            raise CommandError("This app does not exist")

        do_delete = options["yes"]
        if not options["yes"]:
            confirm = input(f"Are you sure you want to delete {app.name}? Y/n\n")
            do_delete = confirm.lower() in ("y", "yes")

        if do_delete:
            self.stdout.write(f"Deleting {app.name}")
            app.delete()
        else:
            self.stdout.write(f"App {app.name} will not be deleted")
