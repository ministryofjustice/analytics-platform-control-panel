from django.core.management.base import BaseCommand, CommandError
from django.core.validators import validate_slug
from django.core.exceptions import ValidationError

from controlpanel.api.auth0 import ManagementAPI
from controlpanel.api.models import App, User


class Command(BaseCommand):
    help = "Creates a new auth0 email user (if necessary) and gives app access"

    def add_arguments(self, parser):
        parser.add_argument(
            "--email",
            type=str,
            required=True,
            help="The email address of the user to associate",
        )
        parser.add_argument(
            "--app",
            type=str,
            required=True,
            help="Slug of the app to add the user to",
        )

    def get_app(self, slug: str) -> App:
        app = None

        try:
            validate_slug(slug)
        except ValidationError:
            raise CommandError(f"App name '{slug}' should be a valid slug")

        try:
            app = App.objects.get(slug=slug)
        except App.DoesNotExist:
            raise CommandError("This app does not exist")

        return app

    def get_or_create_user(self, email: str) -> str:
        """
        Given an email address, this method will attempt to find an existing
        user with this email address (and the appropriate connection type) and
        then return the user's ID.  If this fails, a new user is created and
        the new user ID is returned instead.
        """
        if not "@" in email:
            raise CommandError(
                "Extensive parsing has determined the user's email is not valid"
            )

        users = ManagementAPI().get_users_email_search(email, connection="email")

        first_response = next(iter(users), None)
        if first_response:
            return first_response["user_id"]

        return self.create_auth_user(email)

    def create_auth_user(self, email: str) -> str:
        return ManagementAPI().create_user(
            email=email, email_verified=True, connection="email"
        )

    def handle(self, *args, **options):
        app_slug = options.get("app", "").lower()
        email = options.get("email", "").lower()

        app = self.get_app(app_slug)
        user = self.get_or_create_user(email)

        # TODO: Add the user id to the app using the extension API
