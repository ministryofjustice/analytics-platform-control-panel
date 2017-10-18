from django.test import override_settings
import jwt
from model_mommy import mommy
from rest_framework.reverse import reverse
from rest_framework.status import HTTP_403_FORBIDDEN, HTTP_200_OK
from rest_framework.test import APITestCase

from control_panel_api.authentication import Auth0JWTAuthentication


# Decode token at https://jwt.io/
GOOD_TOKEN = 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJlbWFpbCI6ImphbWVzQGptb3ouY28udWsiLCJuYW1lIjoiSmFtZXMgTW9ycmlzIiwiYXVkIjoiYXVkaWVuY2UiLCJzdWIiOiJnaXRodWJ8MTIzNDUifQ.Vfvhtm_TXbtOBKcIWed0YzVH7gIKlSdzg36bbIK6UZ4'  # noqa


class Auth0JWTAuthenticationTestCase(APITestCase):

    def setUp(self):
        self.user = mommy.make(
            'control_panel_api.User',
            username='james',
            auth0_id='github|12345',
            is_superuser=True
        )

    def get_user(self):
        return self.client.get(
            reverse('user-detail', args=[self.user.auth0_id]))

    def assert_access_denied(self):
        self.assertEqual(HTTP_403_FORBIDDEN, self.get_user().status_code)

    def assert_authenticated(self):
        self.assertEqual(HTTP_200_OK, self.get_user().status_code)

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
        # assert the token is good
        decoded = jwt.decode(GOOD_TOKEN, key='secret', audience='audience')
        self.assertEqual(decoded['sub'], 'github|12345')
        self.client.credentials(HTTP_AUTHORIZATION=f'JWT {GOOD_TOKEN}')
        self.assert_authenticated()
