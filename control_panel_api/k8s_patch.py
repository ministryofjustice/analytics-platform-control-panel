import base64
import datetime
import json
from datetime import timezone

import kubernetes
from kubernetes.config.kube_config import _is_expired


def load_token(self):
    if 'auth-provider' not in self._user:
        return

    provider = self._user['auth-provider']

    if ('name' not in provider
            or 'config' not in provider
            or provider['name'] != 'oidc'):
        return

    parts = provider['config']['id-token'].split('.')

    if len(parts) != 3:  # Not a valid JWT
        return None

    jwt_attributes = json.loads(
        base64.b64decode(parts[1] + '==').decode('utf-8')
    )

    expire = jwt_attributes.get('exp')

    if ((expire is not None) and
        (_is_expired(
            datetime.datetime.fromtimestamp(expire, tz=timezone.utc)))):
        self._refresh_oidc(provider)

        if self._config_persister:
            self._config_persister(self._config.value)

    self.token = f"Bearer {provider['config']['id-token']}"

    return self.token


kubernetes.config.kube_config.KubeConfigLoader._load_oid_token = load_token
