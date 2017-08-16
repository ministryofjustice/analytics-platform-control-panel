from model_mommy import mommy
from rest_framework.reverse import reverse
from rest_framework.status import HTTP_200_OK, HTTP_204_NO_CONTENT, HTTP_404_NOT_FOUND, HTTP_201_CREATED
from rest_framework.test import APITestCase


class AuthenticatedClientMixin(object):
    def setUp(self):
        super(AuthenticatedClientMixin, self).setUp()
        self.client.force_login(mommy.make('control_panel_api.User'))


class UserViewTest(AuthenticatedClientMixin, APITestCase):
    def setUp(self):
        super(UserViewTest, self).setUp()
        self.fixture = mommy.make('control_panel_api.User')
        self.client.force_authenticate(self.fixture)

    def test_list(self):
        response = self.client.get(reverse('user-list'))
        self.assertEqual(HTTP_200_OK, response.status_code)
        self.assertEqual(len(response.data['results']), 2)

    def test_detail(self):
        response = self.client.get(reverse('user-detail', (self.fixture.id,)))
        self.assertEqual(HTTP_200_OK, response.status_code)
        self.assertIn('email', response.data)
        self.assertIn('url', response.data)
        self.assertIn('username', response.data)
        self.assertIn('groups', response.data)
        self.assertIn('id', response.data)
        self.assertEqual(5, len(response.data))

    def test_delete(self):
        response = self.client.delete(reverse('user-detail', (self.fixture.id,)))
        self.assertEqual(HTTP_204_NO_CONTENT, response.status_code)

        response = self.client.get(reverse('user-detail', (self.fixture.id,)))
        self.assertEqual(HTTP_404_NOT_FOUND, response.status_code)

    def test_create(self):
        data = {'username': 'foo'}
        response = self.client.post(reverse('user-list'), data)
        self.assertEqual(HTTP_201_CREATED, response.status_code)

    def test_update(self):
        data = {'username': 'foo'}
        response = self.client.put(reverse('user-detail', (self.fixture.id,)), data)
        self.assertEqual(HTTP_200_OK, response.status_code)
        self.assertEqual(data['username'], response.data['username'])


class AppViewTest(AuthenticatedClientMixin, APITestCase):
    def setUp(self):
        super(AppViewTest, self).setUp()
        mommy.make('control_panel_api.App')
        self.fixture = mommy.make('control_panel_api.App')

    def test_list(self):
        response = self.client.get(reverse('app-list'))
        self.assertEqual(HTTP_200_OK, response.status_code)
        self.assertEqual(len(response.data['results']), 2)

    def test_detail(self):
        response = self.client.get(reverse('app-detail', (self.fixture.id,)))
        self.assertEqual(HTTP_200_OK, response.status_code)
        self.assertIn('id', response.data)
        self.assertIn('name', response.data)
        self.assertIn('slug', response.data)
        self.assertIn('repo_url', response.data)
        self.assertEqual(4, len(response.data))

    def test_delete(self):
        response = self.client.delete(reverse('app-detail', (self.fixture.id,)))
        self.assertEqual(HTTP_204_NO_CONTENT, response.status_code)

        response = self.client.get(reverse('app-detail', (self.fixture.id,)))
        self.assertEqual(HTTP_404_NOT_FOUND, response.status_code)

    def test_create(self):
        data = {'name': 'foo'}
        response = self.client.post(reverse('app-list'), data)
        self.assertEqual(HTTP_201_CREATED, response.status_code)

    def test_update(self):
        data = {'name': 'foo'}
        response = self.client.put(reverse('app-detail', (self.fixture.id,)), data)
        self.assertEqual(HTTP_200_OK, response.status_code)
        self.assertEqual(data['name'], response.data['name'])
