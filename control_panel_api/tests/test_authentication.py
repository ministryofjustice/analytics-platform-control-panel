from unittest.mock import MagicMock, patch

from django.test import override_settings
from jose import jwk, jwt
from jose.exceptions import JWTError
from model_mommy import mommy
from requests.exceptions import Timeout
from rest_framework.reverse import reverse
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_403_FORBIDDEN,
)
from rest_framework.test import APITestCase

from control_panel_api.models import User
from control_panel_api.tests import PRIVATE_KEY, PUBLIC_KEY

KID = 'mykid'


def build_jwt(claim=None, headers=None):
    default_claim = {
        'email': 'test@example.com',
        'name': 'Test User',
        'aud': 'audience',
        'sub': 'github|12345',
        'nickname': 'test',
    }

    default_headers = {
        'kid': KID
    }

    if claim:
        default_claim.update(claim)

    if headers:
        default_headers.update(headers)

    return jwt.encode(default_claim, PRIVATE_KEY, 'RS256', default_headers)


def build_jwt_from_user(user):
    return build_jwt({
        'sub': user.auth0_id,
        'nickname': user.username,
        'name': user.name,
        'email': user.email
    })


def get_jwks():
    jwk_key = jwk.construct(PUBLIC_KEY, 'RS256')

    jwk_dict = jwk_key.to_dict()
    jwk_dict['kid'] = KID

    return {'keys': [jwk_dict]}


mock_get_keys = MagicMock()
mock_get_keys.return_value = get_jwks()


@override_settings(OIDC_DOMAIN='dev-analytics-moj.eu.auth0.com',
                   OIDC_CLIENT_SECRET='secret',
                   OIDC_CLIENT_ID='audience')
@patch('control_panel_api.aws.aws.client', MagicMock())
@patch('control_panel_api.helm.helm.config_user', MagicMock())
@patch('control_panel_api.helm.helm.init_user', MagicMock())
class Auth0JWTAuthenticationTestCase(APITestCase):
    def setUp(self):
        self.user = mommy.make(
            'control_panel_api.User',
            email='test@example.com',
            name='Test User',
            username='test',
            auth0_id='github|12345',
            is_superuser=True
        )

    def get_user(self, user):
        return self.client.get(
            reverse('user-detail', args=[user.auth0_id]))

    def assert_status_code(self, code):
        r = self.get_user(self.user)
        self.assertEqual(code, r.status_code, r.content.decode('utf8'))

    def assert_access_denied(self):
        self.assert_status_code(HTTP_403_FORBIDDEN)

    def assert_authenticated(self):
        self.assert_status_code(HTTP_200_OK)

    def test_user_can_not_view(self):
        self.assert_access_denied()

    def test_bad_header(self):
        self.client.credentials(HTTP_AUTHORIZATION='FOO bar')
        self.assert_access_denied()

    def test_bad_token(self):
        self.client.credentials(HTTP_AUTHORIZATION='JWT bar')
        self.assert_access_denied()

    @patch('control_panel_api.authentication.get_jwks')
    def test_bad_request_for_jwks(self, mock_request_get):
        mock_request_get.side_effect = Timeout("test_bad_request_for_jwks")

        token = build_jwt()

        self.client.credentials(HTTP_AUTHORIZATION=f'JWT {token}')
        self.assert_access_denied()

    @patch('control_panel_api.authentication.get_jwks', mock_get_keys)
    def test_jwk_kid_keyerror(self):
        token = build_jwt(headers={'kid': 'notmatching'})

        self.client.credentials(HTTP_AUTHORIZATION=f'JWT {token}')
        self.assert_access_denied()

    @patch('control_panel_api.authentication.get_jwks', mock_get_keys)
    @patch('jose.jwt.decode')
    def test_decode_jwt_error(self, mock_decode):
        mock_decode.side_effect = JWTError("test_decode_jwt_error")

        token = build_jwt()

        self.client.credentials(HTTP_AUTHORIZATION=f'JWT {token}')
        self.assert_access_denied()

    @patch('control_panel_api.authentication.get_jwks', mock_get_keys)
    def test_good_token(self):
        token = build_jwt()

        self.client.credentials(HTTP_AUTHORIZATION=f'JWT {token}')
        self.assert_authenticated()

    @patch('control_panel_api.authentication.User.helm_create')
    @patch('control_panel_api.authentication.User.aws_create_role')
    @patch('control_panel_api.authentication.get_jwks', mock_get_keys)
    def test_unknown_valid_user_is_created(self, mock_aws_create_role, mock_helm_create):
        new_user = mommy.prepare(
            'control_panel_api.User',
            email='new@example.com',
            name='new User',
            username='new',
            auth0_id='github|12346',
            is_superuser=False,
        )

        token = build_jwt_from_user(new_user)

        self.client.credentials(HTTP_AUTHORIZATION=f'JWT {token}')
        self.get_user(new_user)

        created_user = User.objects.get(pk=new_user.auth0_id)
        self.assertIsNotNone(created_user)
        self.assertEqual(new_user.auth0_id, created_user.auth0_id)
        self.assertEqual(new_user.username, created_user.username)
        self.assertEqual(new_user.name, created_user.name)
        self.assertEqual(new_user.email, created_user.email)

        mock_helm_create.assert_called()
        mock_aws_create_role.assert_called()


@override_settings(OIDC_DOMAIN='dev-analytics-moj.eu.auth0.com',
                   OIDC_CLIENT_SECRET='secret',
                   OIDC_CLIENT_ID='audience')
@patch('control_panel_api.aws.aws.client', MagicMock())
@patch('control_panel_api.helm.helm.config_user', MagicMock())
@patch('control_panel_api.helm.helm.init_user', MagicMock())
class CreateUser(APITestCase):

    @patch('control_panel_api.authentication.get_jwks', mock_get_keys)
    def test_creates_fine(self):
        # user has logged into OIDC to get jwt token
        token = build_jwt()
        self.client.credentials(HTTP_AUTHORIZATION=f'JWT {token}')
        # user makes first request with token- in this case to get his own user
        r = self.client.get(
            reverse('user-detail', args=['github|12345']))
        self.assertEqual(HTTP_200_OK, r.status_code, r.content.decode('utf8'))
        # a suitable user object is created
        self.assertEqual(
            {
                'auth0_id': 'github|12345',
                'email': 'test@example.com',
                'email_verified': False,
                'groups': [],
                'is_superuser': False,
                'name': 'Test User',
                'url': 'http://testserver/users/github%7C12345/',
                'userapps': [],
                'username': 'test',
                'users3buckets': []},
            r.data, r.content.decode('utf8'))
        # it also asked AWS to create a role
        import control_panel_api.aws as aws
        from unittest.mock import call
        self.assertEqual(aws.aws.client.mock_calls[0], call('iam'))
        self.assertEqual(aws.aws.client.mock_calls[1], call().create_role(AssumeRolePolicyDocument='{"Version": "2012-10-17", "Statement": [{"Effect": "Allow", "Principal": {"Service": "ec2.amazonaws.com"}, "Action": "sts:AssumeRole"}, {"Effect": "Allow", "Principal": {"AWS": "arn:aws:iam::123:role/test-k8s-worker-role"}, "Action": "sts:AssumeRole"}, {"Effect": "Allow", "Principal": {"Federated": "arn:aws:iam::123:saml-provider/test"}, "Action": "sts:AssumeRoleWithSAML", "Condition": {"StringEquals": {"SAML:aud": "https://signin.aws.amazon.com/saml"}}}, {"Effect": "Allow", "Principal": {"Federated": "arn:aws:iam::123:oidc-provider/dev-analytics-moj.eu.auth0.com/"}, "Action": "sts:AssumeRoleWithWebIdentity", "Condition": {"StringEquals": {"dev-analytics-moj.eu.auth0.com/:sub": "github|12345"}}}]}', RoleName='test_user_test'))
        self.assertEqual(aws.aws.client.mock_calls[2], call('iam'))
        self.assertEqual(aws.aws.client.mock_calls[3], call().attach_role_policy(PolicyArn='arn:aws:iam::123:policy/test-read-user-roles-inline-policies', RoleName='test_user_test'))

        # also it installed helm charts config_user & init_user
        import control_panel_api.helm as helm
        helm.helm.config_user.assert_called_with('test')
        helm.helm.init_user.assert_called_with('test', 'test@example.com', 'Test User')
