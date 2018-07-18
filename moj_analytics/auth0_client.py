from auth0.v3 import authentication, exceptions
import requests


class AccessTokenError(Exception):
    pass


class APIError(Exception):
    pass


class CreateResourceError(Exception):
    pass


class AddGroupMemberError(Exception):
    pass


class DeleteGroupMemberError(Exception):
    pass


class AddGroupRoleError(Exception):
    pass


class Auth0(object):

    def __init__(self, client_id, client_secret, domain):
        self.client_id = client_id
        self.client_secret = client_secret
        self.domain = domain
        self.apis = {}

    def access_token(self, audience):

        get_token = authentication.GetToken(self.domain)

        try:
            token = get_token.client_credentials(
                self.client_id,
                self.client_secret,
                audience
            )

        except exceptions.Auth0Error as error:

            raise AccessTokenError(
                error,
                self.client_id,
                self.domain,
                audience)

        return token['access_token']

    def access(self, api):
        key = api.__class__.__name__.replace('API', '').lower()
        api.access_token = self.access_token(api.audience)
        setattr(self, key, api)


class API(object):

    def __init__(self, base_url, audience=None):
        self.base_url = base_url.rstrip('/')
        self.audience = audience or base_url
        self.access_token = None
        self._token = None

    def request(self, method, endpoint, **kwargs):
        url = '{base_url}/{endpoint}'.format(
            base_url=self.base_url,
            endpoint=endpoint
        )

        response = requests.request(
            method,
            url,
            headers={
                'Content-Type': 'application/json',
                'Authorization': 'Bearer {}'.format(self.access_token),
            },
            json=kwargs.pop('json', {}),
            **kwargs
        )

        if response.text:
            return response.json()

        return {}

    def create(self, resource):
        endpoint = '{}s'.format(resource.__class__.__name__.lower())

        response = self.request('POST', endpoint, json=resource)

        if 'error' in response:
            raise CreateResourceError(response)

        print('Created {resource}({attrs})'.format(
            resource=resource.__class__.__name__.lower(),
            attrs=', '.join('='.join(map(str, i)) for i in resource.items())))

        return resource.__class__(self, response)

    def get_all(self, resource_class, **kwargs):
        endpoint = '{}s'.format(resource_class.__name__.lower())

        params = dict(
            page=0,
            per_page=100,
            include_totals=True,
            **kwargs
        )

        resources = []
        total = None

        while True:
            response = self.request('GET', endpoint, params=params)
            response.raise_for_status()

            if total is None:
                total = response['total']

            if total != response['total']:
                raise APIError(f'{endpoint} total changed')

            if endpoint in response:
                resources.extend(response[endpoint])

            if len(resources) >= total:
                break

            params['page'] += 1

        return [resource_class(self, r) for r in resources]

    def get(self, resource):
        resources = self.get_all(resource.__class__)

        for other in resources:

            if all(pair in other.items() for pair in resource.items()):
                return other

    def get_or_create(self, resource):
        result = self.get(resource)

        if result is None:
            result = self.create(resource)

        return result


class ManagementAPI(API):

    def __init__(self, domain):
        super(ManagementAPI, self).__init__(
            'https://{domain}/api/v2/'.format(domain=domain))


class AuthorizationAPI(API):
    pass


class Resource(dict):

    def __init__(self, api=None, *args, **kwargs):
        super(Resource, self).__init__(*args, **kwargs)
        self.api = api


class Client(Resource):

    def __init__(self, api=None, *args, **kwargs):
        super(Client, self).__init__(api, *args, **kwargs)
        self['callbacks'] = ['https://{name}/callback'.format(**self)]
        self['app_type'] = 'regular_web'
        self['allowed_origins'] = ['https://{name}'.format(**self)]

    def disable_all_connections(self, ignore=[]):
        ignore = [connection['id'] for connection in ignore]

        connections = self.api.get_all(Connection)

        for connection in connections:

            if connection['id'] in ignore:
                continue

            if self['client_id'] in connection['enabled_clients']:
                connection.disable_client(self)


class Connection(Resource):

    def disable_client(self, client):

        if client['client_id'] in self['enabled_clients']:
            self['enabled_clients'].remove(client['client_id'])

            self.api.request('PATCH', 'connections/{id}'.format(**self), json={
                'enabled_clients': self['enabled_clients']
            })


class User(Resource):
    pass


class AuthzResource(Resource):

    def __init__(self, api=None, *args, **kwargs):
        super(AuthzResource, self).__init__(api, *args, **kwargs)

        if 'description' not in self and 'name' in self:
            self['description'] = self['name']


class Permission(AuthzResource):

    def __init__(self, api=None, *args, **kwargs):
        super(Permission, self).__init__(api, *args, **kwargs)
        self['applicationType'] = 'client'


class Role(AuthzResource):

    def __init__(self, api=None, *args, **kwargs):
        super(Role, self).__init__(api, *args, **kwargs)
        self['applicationType'] = 'client'

    def __getitem__(self, key):

        if key == 'permissions':

            if not self.__contains__(key):
                return []

        return super(Role, self).__getitem__(key)

    def add_permission(self, permission):

        if permission['_id'] in self['permissions']:
            return

        if 'permissions' not in self:
            self['permissions'] = []

        self['permissions'].append(permission['_id'])

        self.api.request('PUT', 'roles/{_id}'.format(**self), json={
           'name': self['name'],
           'description': self['description'],
           'applicationId': self['applicationId'],
           'applicationType': self['applicationType'],
           'permissions': self['permissions'],
        })

        print('Added permission({perm}) to role({role})'.format(
            perm=permission['name'],
            role=self['name']))


class Member(AuthzResource):
    pass


class Group(AuthzResource):

    def add_role(self, role):
        response = self.api.request(
            'PATCH',
            f"groups/{self['_id']}/roles",
            json=[role['_id']]
        )

        if 'error' in response:
            raise AddGroupRoleError(response)

        print('Added role({role}) to group({group})'.format(
            role=role['name'],
            group=self['name']))

    def add_users(self, users):
        response = self.api.request(
            'PATCH',
            f"groups/{self['_id']}/members",
            json=[user['user_id'] for user in users]
        )

        if 'error' in response:
            raise AddGroupMemberError(response)

    def delete_users(self, users):
        response = self.api.request(
            'DELETE',
            f"groups/{self['_id']}/members",
            json=[user['user_id'] for user in users]
        )

        if 'error' in response:
            raise DeleteGroupMemberError(response)

    def get_members(self):
        results = self.api.request(
            'GET', f"groups/{self['_id']}/members")

        return [Member(self, r) for r in results['users']]
