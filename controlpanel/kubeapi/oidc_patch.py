import base64
import json
import tempfile

import kubernetes
import oauthlib.oauth2
from requests_oauthlib import OAuth2Session


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

