
# Third-party
from django.core.management.base import BaseCommand

# First-party/Local
from controlpanel.api.models import App, AppS3Bucket
from controlpanel.api import auth0


class Command(BaseCommand):
    help = "Clear up the redundant resources for migrated apps " \
           "- remove the old auth0 related resources " \
           "- remove old auth0 information from control db" \
           "- remove the apps which are not required any more"

    SCRIPT_LOG_FILE_NAME = "./clear_up_auth0_resources_log.txt"

    EXCEPTION_APPS = ["gold-scorecard-form"]

    def add_arguments(self, parser):
        parser.add_argument(
            "-a", "--apply", action="store_true", help="Apply the actions"
        )

    def _remove_old_auth0_clients(self, app, auth0_instance):
        old_client_info = (app.app_conf or {}).get(App.KEY_WORD_FOR_AUTH_SETTINGS, {}).\
            get(App.DEFAULT_AUTH_CATEGORY, {})
        if not old_client_info:
            self._log_info(f"No old client for {app.slug} - {app.repo_url}")
            return

        self._log_info(f"Removing the old client for {app.slug} - {app.repo_url}")
        if self.apply_action:
            auth0_instance.clear_up_app(old_client_info)

    def _update_db(self, app):
        self._log_info(f"Removing the migration info and old clients for {app.slug} - {app.repo_url}")
        app.description = ""
        if App.DEFAULT_AUTH_CATEGORY in (app.app_conf or {}).get(App.KEY_WORD_FOR_AUTH_SETTINGS, {}):
            del app.app_conf[App.KEY_WORD_FOR_AUTH_SETTINGS][App.DEFAULT_AUTH_CATEGORY]
        if self.apply_action:
            app.save()

    def _remove_application(self, app):
        self._log_info(f"Removing the application {app.slug} - {app.repo_url}")

        """ TODO: how to deal with related bucket? we will output
        the related datasets from this script"""
        # log the related buckets information into file
        related_buckets = AppS3Bucket.objects.filter(app_id=app.id)
        for item in related_buckets:
            self._log_info(f"The app links the bucket - {item.s3bucket.name}")
            # Remove the relationship to avoid removal of the bucket when removing the app
            if self.apply_action:
                item.delete()
        if self.apply_action:
            app.delete()

    def _log_info(self, info):
        self.stdout.write(info)
        with open(self.SCRIPT_LOG_FILE_NAME, "a") as f:
            f.write(info)
            f.write("\n")

    def _clear_up_resources(self, auth0_instance):
        apps = App.objects.all()
        counter = 1
        for app in apps:
            if app.slug in self.EXCEPTION_APPS:
                self._log_info(f"Ignore the application {app.slug}")
                continue

            try:
                self._log_info(f"{counter}--Processing the application {app.slug}")

                self._remove_old_auth0_clients(app, auth0_instance)
                self._update_db(app)
                if "moj-analytical-services" in app.repo_url:
                    self._remove_application(app)
                self._log_info(f"{counter}--Done with the application {app.slug}")
                counter += 1
            except Exception as ex:
                self._log_info(f"Failed to process {app.slug} due to error : {ex.__str__()}")

    def handle(self, *args, **options):
        self.stdout.write("start to scan the apps from database.")
        auth0_instance = auth0.ExtendedAuth0()
        self.apply_action = options.get('apply') or False
        self._clear_up_resources(auth0_instance)
        self.stdout.write("Clean up action has completed.")

