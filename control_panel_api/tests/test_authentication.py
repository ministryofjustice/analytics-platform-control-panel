from django.test import override_settings
from model_mommy import mommy
from rest_framework.reverse import reverse
from rest_framework.status import HTTP_403_FORBIDDEN, HTTP_200_OK
from rest_framework.test import APITestCase

# Decode token at https://jwt.io/
GOOD_TOKEN = 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJlbWFpbCI6ImphbWVzQGptb3ouY28udWsiLCJuYW1lIjoiSmFtZXMgTW9ycmlzIiwiYXVkIjoiYXVkaWVuY2UiLCJzdWIiOiJqYW1lcyJ9.MF9RW-o6g0RFK-G0z1ss07Ru7H4XUz8ZSqeBYHgUWjg'


class Auth0JWTAuthenticationTestCase(APITestCase):
    def setUp(self):
        self.user = mommy.make('control_panel_api.User', username='james')

    def test_user_can_not_view(self):
        response = self.client.get(reverse('user-detail', (self.user.id,)))
        self.assertEqual(HTTP_403_FORBIDDEN, response.status_code)

    def test_bad_header(self):
        self.client.credentials(HTTP_AUTHORIZATION='FOO bar')
        response = self.client.get(reverse('user-detail', (self.user.id,)))
        self.assertEqual(HTTP_403_FORBIDDEN, response.status_code)

    def test_bad_token(self):
        self.client.credentials(HTTP_AUTHORIZATION='JWT bar')
        response = self.client.get(reverse('user-detail', (self.user.id,)))
        self.assertEqual(HTTP_403_FORBIDDEN, response.status_code)

    @override_settings(AUTH0_SECRET='secret', AUTH0_AUDIENCE='audience')
    def test_good_token(self):
        self.client.credentials(HTTP_AUTHORIZATION='JWT {}'.format(GOOD_TOKEN))
        response = self.client.get(reverse('user-detail', (self.user.id,)))
        self.assertEqual(HTTP_200_OK, response.status_code)
