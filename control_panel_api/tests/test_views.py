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
    AppS3Bucket,
    S3Bucket,
    User,
    UserApp,
    UserS3Bucket,
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
        self.assertIn('userapps', response.data)
        self.assertIn('users3buckets', response.data)
        self.assertEqual(8, len(response.data))

    @patch('control_panel_api.models.User.aws_delete_role')
    def test_delete(self, mock_aws_delete_role):
        response = self.client.delete(
            reverse('user-detail', (self.fixture.id,)))
        self.assertEqual(HTTP_204_NO_CONTENT, response.status_code)

        mock_aws_delete_role.assert_called()

        response = self.client.get(reverse('user-detail', (self.fixture.id,)))
        self.assertEqual(HTTP_404_NOT_FOUND, response.status_code)

    @patch('control_panel_api.models.User.aws_create_role')
    def test_create(self, mock_aws_create_role):
        data = {'username': 'foo'}
        response = self.client.post(reverse('user-list'), data)
        self.assertEqual(HTTP_201_CREATED, response.status_code)

        mock_aws_create_role.assert_called()

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
        self.assertIn('userapps', response.data)
        self.assertIn('created_by', response.data)
        self.assertEqual(
            response.data['iam_role_name'],
            self.fixture.iam_role_name,
        )
        self.assertEqual(9, len(response.data))

    @patch('control_panel_api.models.App.aws_delete_role')
    def test_delete(self, mock_aws_delete_role):
        response = self.client.delete(
            reverse('app-detail', (self.fixture.id,)))
        self.assertEqual(HTTP_204_NO_CONTENT, response.status_code)

        mock_aws_delete_role.assert_called()

        response = self.client.get(reverse('app-detail', (self.fixture.id,)))
        self.assertEqual(HTTP_404_NOT_FOUND, response.status_code)

    @patch('control_panel_api.models.App.aws_create_role')
    def test_create(self, mock_aws_create_role):
        data = {'name': 'foo', 'repo_url': 'https://example.com'}
        response = self.client.post(reverse('app-list'), data)
        self.assertEqual(HTTP_201_CREATED, response.status_code)

        mock_aws_create_role.assert_called()

        self.assertEqual(self.superuser.id, response.data['created_by'])

    def test_update(self):
        data = {'name': 'foo', 'repo_url': 'http://foo.com'}
        response = self.client.put(
            reverse('app-detail', (self.fixture.id,)), data)
        self.assertEqual(HTTP_200_OK, response.status_code)
        self.assertEqual(data['name'], response.data['name'])


from django.test import tag
@tag('fluffy')
class AppS3BucketViewTest(AuthenticatedClientMixin, APITestCase):

    def setUp(self):
        super().setUp()

        self.app_1 = mommy.make('control_panel_api.App', name='app_1')
        self.app_2 = mommy.make('control_panel_api.App', name='app_2')

        self.s3_bucket_1 = S3Bucket.objects.create(name="test-bucket-1")
        self.s3_bucket_2 = S3Bucket.objects.create(name="test-bucket-2")
        self.s3_bucket_3 = S3Bucket.objects.create(name="test-bucket-3")

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
        self.assertIn('access_level', response.data)
        self.assertEqual('readonly', response.data['access_level'])
        self.assertEqual(5, len(response.data))

    @patch('control_panel_api.models.AppS3Bucket.aws_delete')
    def test_delete(self, mock_aws_delete):
        response = self.client.delete(
            reverse('apps3bucket-detail', (self.apps3bucket_1.id,)))
        self.assertEqual(HTTP_204_NO_CONTENT, response.status_code)

        mock_aws_delete.assert_called()

        response = self.client.get(
            reverse('apps3bucket-detail', (self.apps3bucket_1.id,)))
        self.assertEqual(HTTP_404_NOT_FOUND, response.status_code)

    @patch('control_panel_api.models.AppS3Bucket.aws_create')
    def test_create(self, mock_aws_create):
        data = {
            'app': self.app_1.id,
            's3bucket': self.s3_bucket_3.id,
            'access_level': AppS3Bucket.READONLY,
        }
        response = self.client.post(reverse('apps3bucket-list'), data)
        self.assertEqual(HTTP_201_CREATED, response.status_code)

        mock_aws_create.assert_called()

    @patch('control_panel_api.models.AppS3Bucket.aws_update')
    def test_update(self, mock_aws_update):
        data = {
            'app': self.app_1.id,
            's3bucket': self.s3_bucket_1.id,
            'access_level': AppS3Bucket.READWRITE,
        }
        response = self.client.put(
            reverse('apps3bucket-detail', (self.apps3bucket_1.id,)), data)
        self.assertEqual(HTTP_200_OK, response.status_code)
        self.assertEqual(data['access_level'], response.data['access_level'])

        mock_aws_update.assert_called()

    def test_update_bad_requests(self):
        fixtures = (
            {
                'app': self.app_2.id,  # when app changed
                's3bucket': self.s3_bucket_1.id,
                'access_level': AppS3Bucket.READWRITE,
            },
            {
                'app': self.app_1.id,  # when s3bucket changed
                's3bucket': self.s3_bucket_2.id,
                'access_level': AppS3Bucket.READWRITE,
            },
        )

        for data in fixtures:
            response = self.client.put(
                reverse('apps3bucket-detail', (self.apps3bucket_1.id,)), data)
            self.assertEqual(HTTP_400_BAD_REQUEST, response.status_code)


class AppUserViewTest(AuthenticatedClientMixin, APITestCase):

    def setUp(self):
        super().setUp()

        self.app_1 = mommy.make('control_panel_api.App', name='app_1')
        self.app_2 = mommy.make('control_panel_api.App', name='app_2')
        self.user_2 = mommy.make('control_panel_api.User')

        self.appuser_1 = UserApp.objects.create(
            user=self.superuser,
            app=self.app_1,
            is_admin=True,
        )
        self.appuser_2 = UserApp.objects.create(
            user=self.user_2,
            app=self.app_1,
            is_admin=True,
        )

    def test_list(self):
        response = self.client.get(reverse('userapp-list'))
        self.assertEqual(HTTP_200_OK, response.status_code)
        self.assertEqual(len(response.data['results']), 2)

    def test_detail(self):
        response = self.client.get(
            reverse('userapp-detail', (self.appuser_1.id,)))
        self.assertEqual(HTTP_200_OK, response.status_code)
        self.assertIn('id', response.data)
        self.assertIn('url', response.data)
        self.assertIn('app', response.data)
        self.assertIn('user', response.data)
        self.assertIn('is_admin', response.data)
        self.assertEqual(True, response.data['is_admin'])
        self.assertEqual(5, len(response.data))

    def test_create(self):
        data = {
            'app': self.app_2.id,
            'user': self.user_2.id,
            'is_admin': False,
        }
        response = self.client.post(reverse('userapp-list'), data)
        self.assertEqual(HTTP_201_CREATED, response.status_code)

    def test_update(self):
        data = {
            'app': self.app_1.id,
            'user': self.user_2.id,
            'is_admin': False,
        }
        response = self.client.put(
            reverse('userapp-detail', (self.appuser_2.id,)), data)
        self.assertEqual(HTTP_200_OK, response.status_code)
        self.assertEqual(data['is_admin'], response.data['is_admin'])

    def test_delete(self):
        response = self.client.delete(
            reverse('userapp-detail', (self.appuser_2.id,)))
        self.assertEqual(HTTP_204_NO_CONTENT, response.status_code)

        response = self.client.get(
            reverse('userapp-detail', (self.appuser_2.id,)))
        self.assertEqual(HTTP_404_NOT_FOUND, response.status_code)

    def test_update_bad_requests(self):
        fixtures = (
            {
                'app': self.app_2.id,  # when app changed
                'user': self.user_2.id,
                'is_admin': True,
            },
            {
                'app': self.app_1.id,  # when user changed
                'user': self.superuser.id,
                'is_admin': True,
            },
        )

        for data in fixtures:
            response = self.client.put(
                reverse('userapp-detail', (self.appuser_2.id,)), data)
            self.assertEqual(HTTP_400_BAD_REQUEST, response.status_code)


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
        self.assertIn('created_by', response.data)
        self.assertEqual(6, len(response.data))

    @patch('control_panel_api.models.S3Bucket.aws_delete')
    def test_delete(self, mock_aws_delete):
        response = self.client.delete(
            reverse('s3bucket-detail', (self.fixture.id,)))
        self.assertEqual(HTTP_204_NO_CONTENT, response.status_code)

        mock_aws_delete.assert_called()

        response = self.client.get(
            reverse('s3bucket-detail', (self.fixture.id,)))
        self.assertEqual(HTTP_404_NOT_FOUND, response.status_code)

    @patch('control_panel_api.models.S3Bucket.aws_create')
    def test_create(self, mock_aws_create):
        data = {'name': 'test-bucket-123'}
        response = self.client.post(reverse('s3bucket-list'), data)
        self.assertEqual(HTTP_201_CREATED, response.status_code)

        self.assertEqual(self.superuser.id, response.data['created_by'])

        mock_aws_create.assert_called()

    def test_create_bad_requests(self):
        fixtures = (
            {'name': self.fixture.name},  # name exists
            {'name': 'ab'},  # name short
            {'name': '127.0.0.1'},  # name invalid
            {'name': '__test_bucket__'},  # name invalid
            {'name': 'badenv-bucketname'},  # name invalid env prefix
            {'name': 'bucketname'},  # name no env prefix
        )

        for data in fixtures:
            response = self.client.post(reverse('s3bucket-list'), data)
            self.assertEqual(HTTP_400_BAD_REQUEST, response.status_code)

    def test_update(self):
        data = {'name': 'test-bucket-updated'}
        response = self.client.put(
            reverse('s3bucket-detail', (self.fixture.id,)), data)
        self.assertEqual(HTTP_200_OK, response.status_code)
        self.assertEqual(data['name'], response.data['name'])


class UserS3BucketViewTest(AuthenticatedClientMixin, APITestCase):
    def setUp(self):
        super().setUp()
        self.user_1 = User.objects.create(username="user-1")
        self.user_2 = User.objects.create(username="user-2")
        self.s3_bucket_1 = S3Bucket.objects.create(name="test-bucket-1")
        self.s3_bucket_2 = S3Bucket.objects.create(name="test-bucket-2")
        self.users3bucket_1 = self.user_1.users3buckets.create(
            s3bucket=self.s3_bucket_1,
            access_level=AppS3Bucket.READONLY,
        )

    def test_list(self):
        response = self.client.get(reverse('users3bucket-list'))
        self.assertEqual(HTTP_200_OK, response.status_code)
        self.assertEqual(len(response.data['results']), 1)

    def test_detail(self):
        response = self.client.get(
            reverse('users3bucket-detail', (self.users3bucket_1.id,)))
        self.assertEqual(HTTP_200_OK, response.status_code)
        self.assertIn('id', response.data)
        self.assertIn('url', response.data)
        self.assertIn('user', response.data)
        self.assertIn('s3bucket', response.data)
        self.assertIn('access_level', response.data)
        self.assertIn('is_admin', response.data)
        self.assertEqual('readonly', response.data['access_level'])
        self.assertEqual(6, len(response.data))

    @patch('control_panel_api.models.UserS3Bucket.aws_create')
    def test_create(self, mock_aws_create):
        data = {
            'user': self.user_2.id,
            's3bucket': self.s3_bucket_1.id,
            'access_level': AppS3Bucket.READONLY,
        }
        response = self.client.post(reverse('users3bucket-list'), data)
        self.assertEqual(HTTP_201_CREATED, response.status_code)

        mock_aws_create.assert_called()

    @patch('control_panel_api.models.UserS3Bucket.aws_delete')
    def test_delete(self, mock_aws_delete):
        response = self.client.delete(
            reverse('users3bucket-detail', (self.users3bucket_1.id,)))
        self.assertEqual(HTTP_204_NO_CONTENT, response.status_code)

        mock_aws_delete.assert_called()

        response = self.client.get(
            reverse('users3bucket-detail', (self.users3bucket_1.id,)))
        self.assertEqual(HTTP_404_NOT_FOUND, response.status_code)

    @patch('control_panel_api.models.UserS3Bucket.aws_update')
    def test_update(self, mock_aws_update):
        data = {
            'user': self.user_1.id,
            's3bucket': self.s3_bucket_1.id,
            'access_level': UserS3Bucket.READWRITE,
        }
        response = self.client.put(
            reverse('users3bucket-detail', (self.users3bucket_1.id,)), data)
        self.assertEqual(HTTP_200_OK, response.status_code)
        self.assertEqual(data['access_level'], response.data['access_level'])

        mock_aws_update.assert_called()

    def test_update_bad_requests(self):
        fixtures = (
            {
                'user': self.user_2.id,  # when app changed
                's3bucket': self.s3_bucket_1.id,
                'access_level': UserS3Bucket.READWRITE,
            },
            {
                'user': self.user_1.id,  # when s3bucket changed
                's3bucket': self.s3_bucket_2.id,
                'access_level': UserS3Bucket.READWRITE,
            },
        )

        for data in fixtures:
            response = self.client.put(
                reverse('users3bucket-detail', (self.users3bucket_1.id,)), data)
            self.assertEqual(HTTP_400_BAD_REQUEST, response.status_code)
