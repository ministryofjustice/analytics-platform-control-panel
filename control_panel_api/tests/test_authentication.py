from django.test import override_settings
import jwt
from model_mommy import mommy
from rest_framework.reverse import reverse
from rest_framework.status import HTTP_403_FORBIDDEN, HTTP_200_OK
from rest_framework.test import APITestCase


def build_jwt(user, audience, secret):
    return jwt.encode(
        {
            'email': user.email,
            'name': user.name,
            'aud': audience,
            'sub': user.auth0_id
        },
        secret,
        algorithm='HS256'
    ).decode('utf8')


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

    def test_user_can_not_view(self):
        self.assert_access_denied()

    def test_bad_header(self):
        self.client.credentials(HTTP_AUTHORIZATION='FOO bar')
        self.assert_access_denied()

    def test_bad_token(self):
        self.client.credentials(HTTP_AUTHORIZATION='JWT bar')
        self.assert_access_denied()

    @override_settings(AUTH0_CLIENT_SECRET='secret', AUTH0_CLIENT_ID='audience')
    def test_good_token(self):

        token = build_jwt(self.user, 'audience', 'secret')

        self.client.credentials(HTTP_AUTHORIZATION='JWT {}'.format(token))
        self.assert_authenticated()
