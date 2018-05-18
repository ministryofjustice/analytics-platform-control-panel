from collections.abc import Mapping
from urllib.parse import urljoin

import requests


class Concourse(object):

    def __init__(self, url, team, username, password):
        self.base_url = url
        self.api_base_url = urljoin(url, '/api/v1/')
        self.session = requests.Session()
        self.team = team
        self.username = username
        self.password = password
        self._pipelines = None

    @property
    def logged_in(self):
        return 'Authorization' in self.session.headers

    def login(self):
        if self.logged_in:
            return

        login_url = f'{self.base_url}/auth/basic/token?team_name={self.team}'
        response = requests.get(login_url, auth=(self.username, self.password))
        response.raise_for_status()
        token = response.json()
        self.session.headers.update({
            'Authorization': f'{token["type"]} {token["value"]}'})

    @property
    def pipelines(self):
        if self._pipelines is None:
            return PipelineMap(self)
        return self._pipelines

    def request(self, endpoint, method='GET', data=None, headers={}, **params):
        if not self.logged_in:
            self.login()

        if data is not None:
            headers['content-type'] = 'application/x-yaml'

        response = self.session.request(
            method,
            urljoin(self.api_base_url, endpoint),
            headers=headers,
            data=data,
            params=params)

        response.raise_for_status()

        return response


class PipelineMap(Mapping):

    def __init__(self, concourse):
        self.concourse = concourse
        items = concourse.request(f'teams/{concourse.team}/pipelines').json()
        self._pipelines = dict([
            (item['name'], Pipeline(concourse, **item))
            for item in items
        ])

    def __getitem__(self, key):
        return self._pipelines[key]

    def __setitem__(self, key, value):
        previous_version = None
        if key in self._pipelines:
            previous_version = self[key].config.version
        self.concourse.request(
            f'teams/{self.concourse.team}/pipelines/{key}/config',
            method='PUT',
            headers={
                'x-concourse-config-version': previous_version},
            data=str(value))
        self._pipelines[key] = Pipeline(
            self.concourse,
            name=key,
            team_name=self.concourse.team)

    def __delitem__(self, key):
        if key in self._pipelines:
            self.concourse.request(
                f'teams/{self.concourse.team}/pipelines/{key}',
                method='DELETE')
        del self._pipelines[key]

    def __iter__(self):
        return iter(self._pipelines)

    def __len__(self):
        return len(self._pipelines)


class Pipeline(object):

    def __init__(self, concourse, paused=True, public=False, **kwargs):
        self.concourse = concourse
        self.__dict__.update(kwargs)
        self.paused = paused
        self.public = public
        self._config = None

    @property
    def config(self):
        if self._config is None:
            response = self.concourse.request(
                f'teams/{self.team_name}/pipelines/{self.name}/config')
            self._config = PipelineConfig.from_response(response)
        return self._config

    @config.setter
    def config(self, value):
        self.concourse.request(
            f'teams/{self.team_name}/pipelines/{self.name}/config',
            method='PUT',
            headers={ 'x-concourse-config-version': self.config.version },
            data=str(value))
        self._config = None


class PipelineConfig(object):

    def __init__(self, version, config, errors, raw_config):
        self.version = version
        self.config = config
        self.errors = errors
        self._raw_config = raw_config

    @classmethod
    def from_response(cls, response):
        return PipelineConfig(
            version=response.headers.get('X-Concourse-Config-Version'),
            **response.json())


class WebappPipeline(Pipeline):

    @property
    def config(self):
        return ''
