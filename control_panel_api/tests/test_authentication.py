from unittest.mock import MagicMock, patch

import jwt
from django.test import override_settings
from model_mommy import mommy
from rest_framework.reverse import reverse
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_403_FORBIDDEN,
    HTTP_404_NOT_FOUND,
)
from rest_framework.test import APITestCase

from control_panel_api.aws import aws
from control_panel_api.helm import helm
from control_panel_api.models import User


def build_jwt(user, audience, secret):
    return jwt.encode(
        {
            'email': user.email,
            'name': user.name,
            'aud': audience,
            'sub': user.auth0_id,
            'nickname': user.username,
        },
        secret,
        algorithm='HS256'
    ).decode('utf8')


@override_settings(OIDC_CLIENT_SECRET='secret', OIDC_CLIENT_ID='audience')
@patch.object(aws, 'client', MagicMock())
@patch.object(helm, 'config_user', MagicMock())
@patch.object(helm, 'init_user', MagicMock())
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

    def get_user(self):
        return self.client.get(
            reverse('user-detail', args=[self.user.auth0_id]))

    def assert_status_code(self, code):
        r = self.get_user()
        self.assertEqual(code, r.status_code, r.content.decode('utf8'))

    def assert_access_denied(self):
        self.assert_status_code(HTTP_403_FORBIDDEN)

    def assert_authenticated(self):
        self.assert_status_code(HTTP_200_OK)

    def assert_not_found(self):
        self.assert_status_code(HTTP_404_NOT_FOUND)

    def test_user_can_not_view(self):
        self.assert_access_denied()

    def test_bad_header(self):
        self.client.credentials(HTTP_AUTHORIZATION='FOO bar')
        self.assert_access_denied()

    def test_bad_token(self):
        self.client.credentials(HTTP_AUTHORIZATION='JWT bar')
        self.assert_access_denied()

    def test_good_token(self):
        token = build_jwt(self.user, 'audience', 'secret')

        self.client.credentials(HTTP_AUTHORIZATION=f'JWT {token}')
        self.assert_authenticated()

    def test_unknown_valid_user_is_created(self):
        new_user = mommy.prepare(
            'control_panel_api.User',
            email='new@example.com',
            name='new User',
            username='new',
            auth0_id='github|12346',
            is_superuser=False,
        )

        token = build_jwt(new_user, 'audience', 'secret')

        self.client.credentials(HTTP_AUTHORIZATION=f'JWT {token}')
        # 404 is raised before object permissions are checked
        self.assert_not_found()

        created_user = User.objects.get(pk=new_user.auth0_id)
        self.assertIsNotNone(created_user)
        self.assertEqual(new_user.auth0_id, created_user.auth0_id)
        self.assertEqual(new_user.username, created_user.username)
        self.assertEqual(new_user.name, created_user.name)
        self.assertEqual(new_user.email, created_user.email)
