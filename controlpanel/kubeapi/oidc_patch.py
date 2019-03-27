import base64
import datetime
from datetime import timezone
import json
import logging
import os
import tempfile

import kubernetes
from kubernetes.config.kube_config import _is_expired
import oauthlib.oauth2
from requests_oauthlib import OAuth2Session
import yaml


log = logging.getLogger(__name__)


def load_token(self, provider):
    if "config" not in provider:
        return

    parts = provider["config"]["id-token"].split(".")

    if len(parts) != 3:  # Not a valid JWT
        return None

    padding = (4 - len(parts[1]) % 4) * "="

    jwt_attributes = json.loads(base64.b64decode(parts[1] + padding).decode("utf-8"))

    expire = jwt_attributes.get("exp")

    if (expire is not None) and (
        _is_expired(datetime.datetime.fromtimestamp(expire, tz=timezone.utc))
    ):
        log.debug(provider["config"]["idp-issuer-url"])

        self._refresh_oidc(provider)

        if self._config_persister:
            self._config_persister(self._config.value)

    self.token = f"Bearer {provider['config']['id-token']}"

    return self.token


kubernetes.config.kube_config.KubeConfigLoader._load_oid_token = load_token


def refresh_oidc(self, provider):
    config = kubernetes.client.Configuration()

    if 'idp-certificate-authority-data' in provider['config']:
        ca_cert = tempfile.NamedTemporaryFile(delete=True)

        ca_data = provider['config']['idp-certificate-authority-data']

        padding = (4 - len(ca_data) % 4) * "="

        cert = base64.b64decode(ca_data + padding).decode('utf-8')

        with open(ca_cert.name, 'w') as fh:
            fh.write(cert)

        config.ssl_ca_cert = ca_cert.name

    else:
        config.verify_ssl = False

    client = kubernetes.client.ApiClient(configuration=config)

    response = client.request(
        method="GET",
        url="%s/.well-known/openid-configuration"
        % provider['config']['idp-issuer-url'].rstrip('/'),
    )

    if response.status != 200:
        return

    response = json.loads(response.data)

    request = OAuth2Session(
        client_id=provider['config']['client-id'],
        token=provider['config']['refresh-token'],
        auto_refresh_kwargs={
            'client_id': provider['config']['client-id'],
            'client_secret': provider['config']['client-secret'],
        },
        auto_refresh_url=response['token_endpoint'],
    )

    try:
        refresh = request.refresh_token(
            token_url=response['token_endpoint'],
            refresh_token=provider['config']['refresh-token'],
            auth=(provider['config']['client-id'],
                  provider['config']['client-secret']),
            verify=config.ssl_ca_cert if config.verify_ssl else None,
        )
    except oauthlib.oauth2.rfc6749.errors.InvalidClientIdError:
        return

    provider['config'].value['id-token'] = refresh['id_token']
    provider['config'].value['refresh-token'] = refresh['refresh_token']


kubernetes.config.kube_config.KubeConfigLoader._refresh_oidc = refresh_oidc


def get_yaml_config_loader(filename, **kwargs):
    with open(filename) as f:
        return kubernetes.config.kube_config.KubeConfigLoader(
            config_dict=yaml.load(f, Loader=yaml.FullLoader),
            config_base_path=os.path.abspath(os.path.dirname(filename)),
            **kwargs)


kubernetes.config.kube_config._get_kube_config_loader_for_yaml_file = get_yaml_config_loader
