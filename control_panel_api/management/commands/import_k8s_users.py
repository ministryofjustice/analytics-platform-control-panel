import base64
import logging

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.utils import IntegrityError
from kubernetes import client, config
from kubernetes.config.config_exception import ConfigException

from control_panel_api.models import User
from moj_analytics.auth0_client import Auth0, ManagementAPI, User as Auth0User

logger = logging.getLogger(__name__)


def get_user_secrets():
    try:
        config.load_incluster_config()
    except ConfigException as e:
        logger.error(e)
        config.load_kube_config()

    kubernetes_api = client.CoreV1Api()

    secrets = kubernetes_api.list_secret_for_all_namespaces()

    user_secrets = [
        item.data for item in secrets.items
        if item.metadata.name == 'user-secrets']

    decoded_user_secrets = [
        {k: base64.b64decode(v).decode() for k, v in item.items()}
        for item in user_secrets]

    return decoded_user_secrets


def get_auth0_users():
    api = Auth0(
        settings.OIDC_CLIENT_ID,
        settings.OIDC_CLIENT_SECRET,
        settings.OIDC_DOMAIN
    )
    api.access(ManagementAPI(settings.OIDC_DOMAIN))

    return api.management.get_all(Auth0User, 'connection=github')


def get_auth0_ids():
    auth0_id_by_nickname = {
        item['nickname'].lower(): item['user_id']
        for item in get_auth0_users()}

    return auth0_id_by_nickname


class Command(BaseCommand):
    help = "Import Kubernetes user-secrets data into the User.  " \
           "Uses KUBECONFIG envvar or defaults to ~/.kube/config"

    def handle(self, *args, **options):
        user_secrets = get_user_secrets()

        auth0_id_by_nickname = get_auth0_ids()

        users_added = 0
        for item in user_secrets:
            username = item['username']
            email = item['email']
            name = item['fullname']

            try:
                auth0_id = auth0_id_by_nickname[username.lower()]
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
