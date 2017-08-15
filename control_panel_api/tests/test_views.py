from model_mommy import mommy
from rest_framework.reverse import reverse
from rest_framework.status import HTTP_200_OK, HTTP_204_NO_CONTENT, HTTP_404_NOT_FOUND, HTTP_201_CREATED
from rest_framework.test import APITestCase


class UserViewTest(APITestCase):
    def setUp(self):
        mommy.make('auth.User')
        self.user = mommy.make('auth.User', is_staff=True)
        self.client.force_authenticate(self.user)

    def test_list(self):
        response = self.client.get(reverse('user-list'))
        self.assertEqual(HTTP_200_OK, response.status_code)
        self.assertEqual(len(response.data['results']), 2)

    def test_detail(self):
        response = self.client.get(reverse('user-detail', (self.user.id,)))
        self.assertEqual(HTTP_200_OK, response.status_code)
        self.assertIn('email', response.data)
        self.assertIn('url', response.data)
        self.assertIn('username', response.data)
        self.assertIn('groups', response.data)

    def test_delete(self):
        response = self.client.delete(reverse('user-detail', (self.user.id,)))
        self.assertEqual(HTTP_204_NO_CONTENT, response.status_code)

        response = self.client.get(reverse('user-detail', (self.user.id,)))
        self.assertEqual(HTTP_404_NOT_FOUND, response.status_code)

    def test_create(self):
        data = {'username': 'foo'}
        response = self.client.post(reverse('user-list'), data)
        self.assertEqual(HTTP_201_CREATED, response.status_code)

    def test_update(self):
        data = {'username': 'foo'}
        response = self.client.put(reverse('user-detail', (self.user.id,)), data)
        self.assertEqual(HTTP_200_OK, response.status_code)
        self.assertEqual(data['username'], response.data['username'])
