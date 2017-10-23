import base64
import logging

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.utils import IntegrityError
from kubernetes import client, config

from control_panel_api.models import User
from moj_analytics.auth0_client import Auth0, ManagementAPI, User as Auth0User

logger = logging.getLogger(__name__)


def get_auth0_users():
    api = Auth0(
        settings.OIDC_CLIENT_ID,
        settings.OIDC_CLIENT_SECRET,
        settings.OIDC_DOMAIN
    )
    api.access(ManagementAPI(settings.OIDC_DOMAIN))

    results = api.management.get_all(Auth0User, 'connection=github')

    return results


class Command(BaseCommand):
    help = "Import Kubernetes user-secrets data into the User.  " \
           "Uses KUBECONFIG envvar or defaults to ~/.kube/config"

    USER_SECRETS_NAME = 'user-secrets'

    def handle(self, *args, **options):
        config.load_kube_config()
        v1 = client.CoreV1Api()

        results = v1.list_secret_for_all_namespaces()

        user_secrets = [
            item.data for item in results.items
            if item.metadata.name == Command.USER_SECRETS_NAME]

        decoded_user_secrets = [
            {k: base64.b64decode(v).decode() for k, v in item.items()}
            for item in user_secrets]

        auth0_users_by_nickname = {
            item['nickname'].lower(): item for item in get_auth0_users()}

        users_added = 0
        for item in decoded_user_secrets:
            username = item['username']
            email = item['email']
            name = item['fullname']

            try:
                auth0_id = auth0_users_by_nickname[username.lower()]['user_id']
            except KeyError:
                logger.warning(f"User {username} not found in auth0")
                continue

            try:
                User.objects.create(
                    auth0_id=auth0_id,
                    username=username,
                    email=email,
                    name=name,
                )
                users_added += 1
                logger.info(f"Imported {username} {email} {auth0_id}")
            except IntegrityError:
                logger.warning(
                    f"Existing {username} {email} {auth0_id} skipped")

        self.stdout.write(f"Imported {users_added} users")
