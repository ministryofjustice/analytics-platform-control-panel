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

from control_panel_api.models import (
    App,
    AppS3Bucket,
    S3Bucket,
)


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
        self.assertIn('apps3buckets', response.data)
        self.assertEqual(6, len(response.data))

    @patch('boto3.client')
    def test_delete(self, mock_client):
        response = self.client.delete(
            reverse('app-detail', (self.fixture.id,)))
        self.assertEqual(HTTP_204_NO_CONTENT, response.status_code)

        response = self.client.get(reverse('app-detail', (self.fixture.id,)))
        self.assertEqual(HTTP_404_NOT_FOUND, response.status_code)

    @patch('control_panel_api.services.app_delete')
    def test_delete_deletes_app_iam_role(self, app_delete):
        self.client.delete(reverse('app-detail', (self.fixture.id,)))

        app_delete.assert_called_with(self.fixture.slug)

    @patch('boto3.client')
    def test_create(self, mock_client):
        data = {'name': 'foo'}
        response = self.client.post(reverse('app-list'), data)
        self.assertEqual(HTTP_201_CREATED, response.status_code)

    @patch('control_panel_api.services.app_create')
    def test_create_creates_app_iam_role(self, app_create):
        data = {'name': 'foo'}
        response = self.client.post(reverse('app-list'), data)

        app = App.objects.get(id=response.data["id"])
        app_create.assert_called_with(app.slug)

    def test_update(self):
        data = {'name': 'foo', 'repo_url': 'http://foo.com'}
        response = self.client.put(
            reverse('app-detail', (self.fixture.id,)), data)
        self.assertEqual(HTTP_200_OK, response.status_code)
        self.assertEqual(data['name'], response.data['name'])


class AppS3BucketViewTest(AuthenticatedClientMixin, APITestCase):

    def setUp(self):
        super().setUp()

        # Apps
        self.app_1 = App.objects.create(name="app_1")
        self.app_2 = App.objects.create(name="app_2")

        # S3 buckets
        self.s3_bucket_1 = S3Bucket.objects.create(name="test-bucket-1")
        self.s3_bucket_2 = S3Bucket.objects.create(name="test-bucket-2")
        self.s3_bucket_3 = S3Bucket.objects.create(name="test-bucket-3")

        # Grant access to buckets
        self.apps3bucket_1 = self.app_1.apps3buckets.create(
            s3bucket=self.s3_bucket_1,
            access_level=AppS3Bucket.READONLY,
        )
        self.apps3bucket_2 = self.app_2.apps3buckets.create(
            s3bucket=self.s3_bucket_2,
            access_level=AppS3Bucket.READONLY,
        )

    def test_list(self):
        response = self.client.get(reverse('apps3bucket-list'))
        self.assertEqual(HTTP_200_OK, response.status_code)
        self.assertEqual(len(response.data['results']), 2)

    def test_detail(self):
        response = self.client.get(
            reverse('apps3bucket-detail', (self.apps3bucket_1.id,)))
        self.assertEqual(HTTP_200_OK, response.status_code)
        self.assertIn('id', response.data)
        self.assertIn('url', response.data)
        self.assertIn('app', response.data)
        self.assertIn('s3bucket', response.data)
        self.assertEqual('readonly', response.data['access_level'])
        self.assertEqual(5, len(response.data))

    def test_delete(self):
        response = self.client.delete(
            reverse('apps3bucket-detail', (self.apps3bucket_1.id,)))
        self.assertEqual(HTTP_204_NO_CONTENT, response.status_code)

        response = self.client.get(
            reverse('apps3bucket-detail', (self.apps3bucket_1.id,)))
        self.assertEqual(HTTP_404_NOT_FOUND, response.status_code)

    @patch('control_panel_api.services.apps3bucket_delete')
    def test_delete_calls_service(self, mock_apps3bucket_delete):
        response = self.client.delete(
            reverse('apps3bucket-detail', (self.apps3bucket_1.id,)))
        self.assertEqual(HTTP_204_NO_CONTENT, response.status_code)

        called_args, _ = mock_apps3bucket_delete.call_args
        self.assertIsInstance(called_args[0], AppS3Bucket)
        self.assertEqual(called_args[0].app.slug, self.apps3bucket_1.app.slug)

    def test_create(self):
        data = {
            'app': self.app_1.id,
            's3bucket': self.s3_bucket_3.id,
            'access_level': AppS3Bucket.READWRITE,
        }
        response = self.client.post(reverse('apps3bucket-list'), data)
        self.assertEqual(HTTP_201_CREATED, response.status_code)

    @patch('control_panel_api.services.apps3bucket_create')
    def test_create_grants_access(self, mock_apps3bucket_create):
        data = {
            'app': self.app_1.id,
            's3bucket': self.s3_bucket_3.id,
            'access_level': AppS3Bucket.READONLY,
        }
        self.client.post(reverse('apps3bucket-list'), data)

        apps3bucket = AppS3Bucket.objects.get(
            app=self.app_1,
            s3bucket=self.s3_bucket_3,
        )

        mock_apps3bucket_create.assert_called_with(apps3bucket)

    def test_update(self):
        data = {
            'app': self.app_1.id,
            's3bucket': self.s3_bucket_1.id,
            'access_level': AppS3Bucket.READWRITE,
        }
        response = self.client.put(
            reverse('apps3bucket-detail', (self.apps3bucket_1.id,)), data)
        self.assertEqual(HTTP_200_OK, response.status_code)
        self.assertEqual(data['access_level'], response.data['access_level'])


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
        self.assertIn('apps3buckets', response.data)
        self.assertEqual(5, len(response.data))

    def test_delete(self):
        response = self.client.delete(
            reverse('s3bucket-detail', (self.fixture.id,)))
        self.assertEqual(HTTP_204_NO_CONTENT, response.status_code)

        response = self.client.get(
            reverse('s3bucket-detail', (self.fixture.id,)))
        self.assertEqual(HTTP_404_NOT_FOUND, response.status_code)

    @patch('control_panel_api.services.bucket_delete')
    def test_delete_calls_apis(self, mock_bucket_delete):
        self.client.delete(reverse('s3bucket-detail', (self.fixture.id,)))
        mock_bucket_delete.assert_called_with('test-bucket-1')

    def test_create_when_valid_data(self):
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

    def test_create_name_valid_env_prefix(self):
        data = {'name': 'test-bucketname-foo-bar'}
        response = self.client.post(reverse('s3bucket-list'), data)
        self.assertEqual(HTTP_201_CREATED, response.status_code)

    def test_create_name_invalid_env_prefix_400(self):
        data = {'name': 'badenv-bucketname'}
        response = self.client.post(reverse('s3bucket-list'), data)
        self.assertEqual(HTTP_400_BAD_REQUEST, response.status_code)

    def test_create_name_no_env_prefix_400(self):
        data = {'name': 'bucketname'}
        response = self.client.post(reverse('s3bucket-list'), data)
        self.assertEqual(HTTP_400_BAD_REQUEST, response.status_code)

    @patch('control_panel_api.services.bucket_create')
    def test_create_calls_apis(self, mock_bucket_create):
        data = {'name': 'test-bucket-123'}
        self.client.post(reverse('s3bucket-list'), data)
        mock_bucket_create.assert_called_with('test-bucket-123')

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
