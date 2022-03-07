from django.core.management.base import BaseCommand, CommandError
from django.core.validators import validate_slug
from django.core.exceptions import ValidationError

from controlpanel.api.models import App

class Command(BaseCommand):
    help = """Delete an app.
              Input: App slug"""

    def add_arguments(self, parser):
        parser.add_argument("slug", type=str)
        parser.add_argument("-y", "--yes", action="store_true")

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

        do_delete = options["yes"]
        if not options["yes"]:
            confirm = input(f"Are you sure you want to delete {app.name}? Y/n\n")
            if confirm in ("Y", "yes"):
                do_delete = True
        
        if do_delete: 
            self.stdout.write(f"Deleting {app.name}")
            app.delete()
        else:
            self.stdout.write(f"App {app.name} will not be deleted")
