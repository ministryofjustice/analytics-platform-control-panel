from unittest.mock import patch

from model_mommy import mommy
from rest_framework.reverse import reverse
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_201_CREATED,
    HTTP_204_NO_CONTENT,
    HTTP_400_BAD_REQUEST,
    HTTP_404_NOT_FOUND,
)
from rest_framework.test import APITestCase


class AuthenticatedClientMixin(object):
    def setUp(self):
        self.superuser = mommy.make(
            'control_panel_api.User', is_superuser=True)
        self.client.force_login(self.superuser)


class UserViewTest(AuthenticatedClientMixin, APITestCase):
    def setUp(self):
        super().setUp()
        self.fixture = mommy.make('control_panel_api.User')

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
        self.assertIn('name', response.data)
        self.assertIn('groups', response.data)
        self.assertIn('id', response.data)
        self.assertEqual(6, len(response.data))

    def test_delete(self):
        response = self.client.delete(
            reverse('user-detail', (self.fixture.id,)))
        self.assertEqual(HTTP_204_NO_CONTENT, response.status_code)

        response = self.client.get(reverse('user-detail', (self.fixture.id,)))
        self.assertEqual(HTTP_404_NOT_FOUND, response.status_code)

    def test_create(self):
        data = {'username': 'foo'}
        response = self.client.post(reverse('user-list'), data)
        self.assertEqual(HTTP_201_CREATED, response.status_code)

    def test_update(self):
        data = {'username': 'foo'}
        response = self.client.put(
            reverse('user-detail', (self.fixture.id,)), data)
        self.assertEqual(HTTP_200_OK, response.status_code)
        self.assertEqual(data['username'], response.data['username'])


class AppViewTest(AuthenticatedClientMixin, APITestCase):
    def setUp(self):
        super().setUp()
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
        self.assertIn('url', response.data)
        self.assertIn('name', response.data)
        self.assertIn('slug', response.data)
        self.assertIn('repo_url', response.data)
        self.assertEqual(5, len(response.data))

    def test_delete(self):
        response = self.client.delete(
            reverse('app-detail', (self.fixture.id,)))
        self.assertEqual(HTTP_204_NO_CONTENT, response.status_code)

        response = self.client.get(reverse('app-detail', (self.fixture.id,)))
        self.assertEqual(HTTP_404_NOT_FOUND, response.status_code)

    def test_create(self):
        data = {'name': 'foo'}
        response = self.client.post(reverse('app-list'), data)
        self.assertEqual(HTTP_201_CREATED, response.status_code)

    def test_update(self):
        data = {'name': 'foo', 'repo_url': 'http://foo.com'}
        response = self.client.put(
            reverse('app-detail', (self.fixture.id,)), data)
        self.assertEqual(HTTP_200_OK, response.status_code)
        self.assertEqual(data['name'], response.data['name'])


class S3BucketViewTest(AuthenticatedClientMixin, APITestCase):
    def setUp(self):
        super().setUp()
        mommy.make('control_panel_api.S3Bucket')
        self.fixture = mommy.make(
            'control_panel_api.S3Bucket', name='test-bucket-1')

    def test_list(self):
        response = self.client.get(reverse('s3bucket-list'))
        self.assertEqual(HTTP_200_OK, response.status_code)
        self.assertEqual(len(response.data['results']), 2)

    def test_detail(self):
        response = self.client.get(
            reverse('s3bucket-detail', (self.fixture.id,)))
        self.assertEqual(HTTP_200_OK, response.status_code)
        self.assertIn('id', response.data)
        self.assertIn('url', response.data)
        self.assertIn('name', response.data)
        self.assertIn('arn', response.data)
        self.assertEqual(4, len(response.data))

    def test_delete(self):
        response = self.client.delete(
            reverse('s3bucket-detail', (self.fixture.id,)))
        self.assertEqual(HTTP_204_NO_CONTENT, response.status_code)

        response = self.client.get(reverse('s3bucket-detail', (self.fixture.id,)))
        self.assertEqual(HTTP_404_NOT_FOUND, response.status_code)

    @patch('boto3.client')
    def test_create_when_valid_data(self, mock_client):
        data = {'name': 'test-bucket-123'}
        response = self.client.post(reverse('s3bucket-list'), data)
        self.assertEqual(HTTP_201_CREATED, response.status_code)

    def test_create_when_name_taken(self):
        data = {'name': self.fixture.name}
        response = self.client.post(reverse('s3bucket-list'), data)
        self.assertEqual(HTTP_400_BAD_REQUEST, response.status_code)

    def test_create_when_name_short(self):
        data = {'name': 'ab'}
        response = self.client.post(reverse('s3bucket-list'), data)
        self.assertEqual(HTTP_400_BAD_REQUEST, response.status_code)

    def test_create_when_name_invalid(self):
        data = {'name': '127.0.0.1'}
        response = self.client.post(reverse('s3bucket-list'), data)
        self.assertEqual(HTTP_400_BAD_REQUEST, response.status_code)

    def test_update_when_valid_data(self):
        data = {'name': 'test-bucket-updated'}
        response = self.client.put(
            reverse('s3bucket-detail', (self.fixture.id,)), data)
        self.assertEqual(HTTP_200_OK, response.status_code)
        self.assertEqual(data['name'], response.data['name'])

    def test_update_when_name_invalid(self):
        data = {'name': '__test_bucket__'}
        response = self.client.put(
            reverse('s3bucket-detail', (self.fixture.id,)), data)
        self.assertEqual(HTTP_400_BAD_REQUEST, response.status_code)
