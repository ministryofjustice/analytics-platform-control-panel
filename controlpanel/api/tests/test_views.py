from subprocess import CalledProcessError
from unittest.mock import MagicMock, patch, call

from botocore.exceptions import ClientError
from django.test import override_settings
from model_mommy import mommy
from rest_framework.reverse import reverse
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_201_CREATED,
    HTTP_204_NO_CONTENT,
    HTTP_400_BAD_REQUEST,
    HTTP_404_NOT_FOUND,
    HTTP_500_INTERNAL_SERVER_ERROR,
)
from rest_framework.test import APITestCase

from control_panel_api.aws import aws
from control_panel_api.models import (
    App,
    AppS3Bucket,
    S3Bucket,
    User,
    UserApp,
    UserS3Bucket,
)
from control_panel_api.tests.fixtures.es import BUCKET_HITS_AGGREGATION
from control_panel_api.tests.test_authentication import (
    build_jwt_from_user,
    mock_get_keys,
)
from moj_analytics.auth0_client import Group as Auth0Group, User as Auth0User


class AuthenticatedClientMixin(object):

    def setUp(self):
        self.superuser = mommy.make(
            'control_panel_api.User', is_superuser=True)
        self.client.force_login(self.superuser)
        super().setUp()


class UserViewTest(AuthenticatedClientMixin, APITestCase):

    def setUp(self):
        super().setUp()
        self.fixture = mommy.make('control_panel_api.User', auth0_id='github|1')
        mommy.make('control_panel_api.UserS3Bucket', user=self.fixture)
        mommy.make('control_panel_api.UserApp', user=self.fixture)

    def test_list(self):
        response = self.client.get(reverse('user-list'))
        self.assertEqual(HTTP_200_OK, response.status_code)
        self.assertEqual(len(response.data['results']), 2)

    def test_detail(self):
        response = self.client.get(
            reverse('user-detail', (self.fixture.auth0_id,)))
        self.assertEqual(HTTP_200_OK, response.status_code)

        expected_fields = {
            'auth0_id',
            'url',
            'username',
            'name',
            'email',
            'groups',
            'userapps',
            'users3buckets',
            'is_superuser',
            'email_verified',
        }
        self.assertEqual(expected_fields, set(response.data))

        userapp = response.data['userapps'][0]
        expected_fields = {'id', 'app', 'is_admin'}
        self.assertEqual(
            expected_fields,
            set(userapp)
        )

        expected_fields = {
            'id',
            'url',
            'name',
            'description',
            'slug',
            'repo_url',
            'iam_role_name',
            'created_by',
        }
        self.assertEqual(
            expected_fields,
            set(userapp['app'])
        )

        users3bucket = response.data['users3buckets'][0]
        expected_fields = {'id', 's3bucket', 'access_level', 'is_admin'}
        self.assertEqual(
            expected_fields,
            set(users3bucket)
        )

        expected_fields = {
            'id',
            'url',
            'name',
            'arn',
            'created_by',
            'is_data_warehouse',
        }
        self.assertEqual(
            expected_fields,
            set(users3bucket['s3bucket'])
        )

    @patch('control_panel_api.models.services.revoke_bucket_access')
    @patch('control_panel_api.models.User.helm_delete')
    @patch('control_panel_api.models.User.aws_delete_role')
    def test_delete(self, mock_aws_delete_role, mock_helm_delete, _):
        response = self.client.delete(
            reverse('user-detail', (self.fixture.auth0_id,)))
        self.assertEqual(HTTP_204_NO_CONTENT, response.status_code)

        mock_aws_delete_role.assert_called()
        mock_helm_delete.assert_called()

        response = self.client.get(
            reverse('user-detail', (self.fixture.auth0_id,)))
        self.assertEqual(HTTP_404_NOT_FOUND, response.status_code)

    @patch('control_panel_api.models.User.helm_create')
    @patch('control_panel_api.models.User.aws_create_role')
    def test_create(self, mock_aws_create_role, mock_helm_create_user):
        username = 'foo'
        data = {'auth0_id': 'github|2', 'username': username}
        response = self.client.post(reverse('user-list'), data)
        self.assertEqual(HTTP_201_CREATED, response.status_code)

        self.assertEqual(data['auth0_id'], response.data['auth0_id'])

        mock_aws_create_role.assert_called()
        mock_helm_create_user.assert_called()

    def test_update(self):
        data = {'username': 'foo', 'auth0_id': 'github|888'}
        response = self.client.put(
            reverse('user-detail', (self.fixture.auth0_id,)), data)
        self.assertEqual(HTTP_200_OK, response.status_code)
        self.assertEqual(data['username'], response.data['username'])
        self.assertEqual(data['auth0_id'], response.data['auth0_id'])

    @patch('control_panel_api.models.User.helm_create')
    @patch('control_panel_api.models.User.aws_create_role')
    def test_aws_error_and_transaction(self, mock_aws_create_role,
                                       mock_helm_create):
        mock_aws_create_role.side_effect = ClientError({"foo": "bar"}, "bar")

        data = {'auth0_id': 'github|3', 'username': 'foo'}
        response = self.client.post(reverse('user-list'), data)
        self.assertEqual(HTTP_500_INTERNAL_SERVER_ERROR, response.status_code)

        mock_aws_create_role.assert_called()
        mock_helm_create.assert_not_called()

        with self.assertRaises(User.DoesNotExist):
            User.objects.get(pk=data['auth0_id'])

    @patch('control_panel_api.models.User.helm_create')
    @patch('control_panel_api.models.User.aws_create_role')
    def test_helm_error_and_transaction(self, mock_aws_create_role,
                                        mock_helm_create):
        mock_helm_create.side_effect = CalledProcessError(1, 'Helm error')

        data = {'auth0_id': 'github|3', 'username': 'foo'}
        response = self.client.post(reverse('user-list'), data)
        self.assertEqual(HTTP_500_INTERNAL_SERVER_ERROR, response.status_code)

        mock_aws_create_role.assert_called()
        mock_helm_create.assert_called()

        with self.assertRaises(User.DoesNotExist):
            User.objects.get(pk=data['auth0_id'])

    @patch('control_panel_api.models.services.grant_read_inline_policies')
    @patch('control_panel_api.models.User.helm_create')
    @patch('control_panel_api.aws.AWSClient.create_role')
    def test_aws_error_existing_ignored(self, mock_create_role,
                                        mock_helm_create, mock_grant_read_inline_policies):
        e = type('EntityAlreadyExistsException', (ClientError,), {})
        mock_create_role.side_effect = e({}, 'CreateRole')

        data = {'auth0_id': 'github|3', 'username': 'foo'}
        response = self.client.post(reverse('user-list'), data)
        self.assertEqual(HTTP_201_CREATED, response.status_code)

        mock_create_role.assert_called()


class AppViewTest(AuthenticatedClientMixin, APITestCase):

    def setUp(self):
        super().setUp()
        mommy.make('control_panel_api.App')
        self.fixture = mommy.make(
            'control_panel_api.App',
            repo_url='https://foo.com'
        )
        mommy.make('control_panel_api.AppS3Bucket', app=self.fixture)
        mommy.make('control_panel_api.UserApp', app=self.fixture)

    def test_list(self):
        response = self.client.get(reverse('app-list'))
        self.assertEqual(HTTP_200_OK, response.status_code)
        self.assertEqual(len(response.data['results']), 2)

    def test_list_filter_by_repo_url(self):
        params = {'repo_url': self.fixture.repo_url}
        response = self.client.get(reverse('app-list'), params)

        self.assertEqual(HTTP_200_OK, response.status_code)
        self.assertEqual(len(response.data['results']), 1)
        app = response.data['results'][0]
        self.assertEqual(app['id'], self.fixture.id)

    def test_detail(self):
        response = self.client.get(reverse('app-detail', (self.fixture.id,)))
        self.assertEqual(HTTP_200_OK, response.status_code)

        expected_fields = {
            'id',
            'url',
            'name',
            'description',
            'slug',
            'repo_url',
            'iam_role_name',
            'created_by',
            'apps3buckets',
            'userapps',
        }
        self.assertEqual(expected_fields, set(response.data))

        self.assertEqual(
            response.data['iam_role_name'],
            self.fixture.iam_role_name,
        )

        apps3bucket = response.data['apps3buckets'][0]
        expected_fields = {'id', 'url', 's3bucket', 'access_level'}
        self.assertEqual(
            expected_fields,
            set(apps3bucket)
        )

        expected_fields = {
            'id',
            'url',
            'name',
            'arn',
            'created_by',
            'is_data_warehouse',
        }
        self.assertEqual(
            expected_fields,
            set(apps3bucket['s3bucket'])
        )

        userapp = response.data['userapps'][0]
        expected_fields = {'id', 'user', 'is_admin'}
        self.assertEqual(
            expected_fields,
            set(userapp)
        )

        expected_fields = {
            'auth0_id',
            'url',
            'username',
            'name',
            'email',
        }
        self.assertEqual(expected_fields, set(userapp['user']))

    @patch('control_panel_api.models.services.revoke_bucket_access')
    @patch('control_panel_api.models.App.aws_delete_role')
    def test_delete(self, mock_aws_delete_role, _):
        response = self.client.delete(
            reverse('app-detail', (self.fixture.id,)))
        self.assertEqual(HTTP_204_NO_CONTENT, response.status_code)

        mock_aws_delete_role.assert_called()

        response = self.client.get(reverse('app-detail', (self.fixture.id,)))
        self.assertEqual(HTTP_404_NOT_FOUND, response.status_code)

    @patch('control_panel_api.models.App.aws_create_role')
    def test_create(self, mock_aws_create_role):
        data = {'name': 'foo', 'repo_url': 'https://example.com.git'}
        response = self.client.post(reverse('app-list'), data)
        self.assertEqual(HTTP_201_CREATED, response.status_code)

        mock_aws_create_role.assert_called()

        self.assertEqual(self.superuser.auth0_id, response.data['created_by'])

        self.assertEqual('https://example.com', response.data['repo_url'])

    def test_update(self):
        data = {'name': 'foo', 'repo_url': 'http://foo.com.git'}
        response = self.client.put(
            reverse('app-detail', (self.fixture.id,)), data)
        self.assertEqual(HTTP_200_OK, response.status_code)
        self.assertEqual(data['name'], response.data['name'])
        self.assertEqual('http://foo.com', response.data['repo_url'])

    @patch('control_panel_api.models.App.aws_create_role')
    def test_aws_error_and_transaction(self, mock_aws_create_role):
        mock_aws_create_role.side_effect = ClientError({"foo": "bar"}, "bar")

        data = {'name': 'not-created', 'repo_url': 'https://example.com.git'}
        response = self.client.post(reverse('app-list'), data)
        self.assertEqual(HTTP_500_INTERNAL_SERVER_ERROR, response.status_code)

        with self.assertRaises(App.DoesNotExist):
            App.objects.get(name=data['name'])

    @patch('control_panel_api.aws.AWSClient.create_role')
    def test_aws_error_existing_ignored(self, mock_create_role):
        e = type('EntityAlreadyExistsException', (ClientError,), {})
        mock_create_role.side_effect = e({}, 'CreateRole')

        data = {'name': 'foo', 'repo_url': 'https://example.com.git'}
        response = self.client.post(reverse('app-list'), data)
        self.assertEqual(HTTP_201_CREATED, response.status_code)

        mock_create_role.assert_called()


class AppCustomersAPIViewTest(AuthenticatedClientMixin, APITestCase):
    def setUp(self):
        super().setUp()
        self.app = mommy.make('control_panel_api.App')

    @patch('control_panel_api.auth0.Auth0Client')
    def test_get(self, mock_auth0client):
        mock_auth0client.return_value.authorization.get.return_value.get_members.return_value = [{
            "email": "a.user@digital.justice.gov.uk",
            "user_id": "email|5955f7ee86da0c1d55foobar",
            "nickname": "a.user",
            "name": "a.user@digital.justice.gov.uk",
            "foo": "bar",
            "baz": "bat",
        }]

        response = self.client.get(
            reverse('appcustomers-list', (self.app.id,)))

        self.assertEqual(HTTP_200_OK, response.status_code)
        self.assertEqual(1, len(response.data))

        expected_fields = {
            'email',
            'user_id',
            'nickname',
            'name',
        }
        self.assertEqual(
            expected_fields,
            set(response.data[0]),
        )

    @patch('control_panel_api.auth0.Auth0Client')
    def test_post(self, mock_auth0_client):
        auth0 = mock_auth0_client.return_value
        authz = auth0.authorization
        mgmt = auth0.management
        group = authz.get.return_value
        emails = [
            'test1@example.com',
            'test2@example.com',
        ]

        def mock_create_user(user):
            return Auth0User(user, user_id=emails.index(user['email']))

        mgmt.create.side_effect = mock_create_user

        def new_user(email):
            return Auth0User(
                email=email,
                email_verified=True,
                connection='email')

        def existing_user(email):
            return Auth0User(new_user(email), user_id=emails.index(email))

        def assert_case(data, all_users, expected_created, expected_added):
            authz.get_all.return_value = all_users

            response = self.client.post(
                reverse('appcustomers-list', (self.app.id,)),
                data)

            self.assertEqual(HTTP_201_CREATED, response.status_code)

            mgmt.create.assert_has_calls(
                [call(user) for user in expected_created],
                any_order=True)

            args, kwargs = group.add_users.call_args
            assert list(args[0]) == expected_added

        assert_case(
            data={'email': 'test1@example.com'},
            all_users=[existing_user('test1@example.com')],
            expected_created=[],
            expected_added=list(map(existing_user, ['test1@example.com'])))

        assert_case(
            data={'email': 'test1@example.com'},
            all_users=[],
            expected_created=map(new_user, ['test1@example.com']),
            expected_added=list(map(existing_user, ['test1@example.com'])))

        assert_case(
            data={'email': 'test1@example.com, test2@example.com'},
            all_users=[],
            expected_created=map(new_user, emails),
            expected_added=list(map(existing_user, emails)))


class AppCustomersDetailAPIView(AuthenticatedClientMixin, APITestCase):
    def setUp(self):
        super().setUp()
        self.fixture = mommy.make('control_panel_api.App')

    @patch('control_panel_api.auth0.Auth0Client')
    def test_delete(self, mock_auth0client):
        user_id = 'email|12345'

        response = self.client.delete(
            reverse('appcustomers-detail', (self.fixture.id, user_id)))

        self.assertEqual(HTTP_204_NO_CONTENT, response.status_code)

        mock_auth0client.return_value.authorization.get.assert_called_with(
            Auth0Group(name=self.fixture.slug)
        )

        mock_auth0client.return_value.authorization.get.return_value.delete_users.assert_called_with(
            [{'user_id': user_id}]
        )


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

        expected_fields = {
            'id',
            'url',
            'app',
            's3bucket',
            'access_level'
        }
        self.assertEqual(
            expected_fields,
            set(response.data),
        )

    @patch('control_panel_api.models.services.revoke_bucket_access')
    def test_delete(self, mock_revoke_bucket_access):
        response = self.client.delete(
            reverse('apps3bucket-detail', (self.apps3bucket_1.id,)))
        self.assertEqual(HTTP_204_NO_CONTENT, response.status_code)

        mock_revoke_bucket_access.assert_called_with(
            self.apps3bucket_1.s3bucket.arn,
            self.apps3bucket_1.aws_role_name(),
        )

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

    @patch('control_panel_api.models.AppS3Bucket.aws_create', MagicMock())
    def test_create_with_s3_data_warehouse_not_allowed(self):
        s3_bucket_app = mommy.make(
            'control_panel_api.S3Bucket', is_data_warehouse=False)

        data = {
            'app': self.app_1.id,
            's3bucket': s3_bucket_app.id,
            'access_level': AppS3Bucket.READONLY,
        }
        response = self.client.post(reverse('apps3bucket-list'), data)
        self.assertEqual(HTTP_201_CREATED, response.status_code)

        s3_bucket = mommy.make(
            'control_panel_api.S3Bucket', is_data_warehouse=True)

        data = {
            'app': self.app_1.id,
            's3bucket': s3_bucket.id,
            'access_level': AppS3Bucket.READONLY,
        }
        response = self.client.post(reverse('apps3bucket-list'), data)
        self.assertEqual(HTTP_400_BAD_REQUEST, response.status_code)


class UserAppViewTest(AuthenticatedClientMixin, APITestCase):

    def setUp(self):
        super().setUp()

        self.app_1 = mommy.make('control_panel_api.App', name='app_1')
        self.app_2 = mommy.make('control_panel_api.App', name='app_2')
        self.user_2 = mommy.make('control_panel_api.User', auth0_id='github|1')

        self.userapp_1 = UserApp.objects.create(
            user=self.superuser,
            app=self.app_1,
            is_admin=True,
        )
        self.userapp_2 = UserApp.objects.create(
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
            reverse('userapp-detail', (self.userapp_1.id,)))
        self.assertEqual(HTTP_200_OK, response.status_code)

        expected_fields = {'id', 'url', 'app', 'user', 'is_admin'}
        self.assertEqual(expected_fields, set(response.data))

        self.assertEqual(True, response.data['is_admin'])

    def test_create(self):
        data = {
            'app': self.app_2.id,
            'user': self.user_2.auth0_id,
            'is_admin': False,
        }
        response = self.client.post(reverse('userapp-list'), data)
        self.assertEqual(HTTP_201_CREATED, response.status_code)

    def test_update(self):
        data = {
            'app': self.app_1.id,
            'user': self.user_2.auth0_id,
            'is_admin': False,
        }
        response = self.client.put(
            reverse('userapp-detail', (self.userapp_2.id,)), data)
        self.assertEqual(HTTP_200_OK, response.status_code)
        self.assertEqual(data['is_admin'], response.data['is_admin'])

    def test_delete(self):
        response = self.client.delete(
            reverse('userapp-detail', (self.userapp_2.id,)))
        self.assertEqual(HTTP_204_NO_CONTENT, response.status_code)

        response = self.client.get(
            reverse('userapp-detail', (self.userapp_2.id,)))
        self.assertEqual(HTTP_404_NOT_FOUND, response.status_code)

    def test_update_bad_requests(self):
        fixtures = (
            {
                'app': self.app_2.id,  # when app changed
                'user': self.user_2.auth0_id,
                'is_admin': True,
            },
            {
                'app': self.app_1.id,  # when user changed
                'user': self.superuser.auth0_id,
                'is_admin': True,
            },
        )

        for data in fixtures:
            response = self.client.put(
                reverse('userapp-detail', (self.userapp_2.id,)), data)
            self.assertEqual(HTTP_400_BAD_REQUEST, response.status_code)


@patch.object(aws, 'client', MagicMock())
class S3BucketViewTest(AuthenticatedClientMixin, APITestCase):

    def setUp(self):
        super().setUp()
        mommy.make('control_panel_api.S3Bucket')
        mommy.make('control_panel_api.S3Bucket', is_data_warehouse=True)
        self.fixture = mommy.make(
            'control_panel_api.S3Bucket', name='test-bucket-1')
        mommy.make('control_panel_api.AppS3Bucket', s3bucket=self.fixture)
        mommy.make('control_panel_api.UserS3Bucket', s3bucket=self.fixture)

    def test_list(self):
        response = self.client.get(reverse('s3bucket-list'))
        self.assertEqual(HTTP_200_OK, response.status_code)
        self.assertEqual(len(response.data['results']), 3)

        response = self.client.get(
            reverse('s3bucket-list') + '?is_data_warehouse=true')
        self.assertEqual(len(response.data['results']), 1)

    def test_detail(self):
        response = self.client.get(
            reverse('s3bucket-detail', (self.fixture.id,)))
        self.assertEqual(HTTP_200_OK, response.status_code)

        expected_s3bucket_fields = {
            'id',
            'url',
            'name',
            'arn',
            'apps3buckets',
            'users3buckets',
            'created_by',
            'is_data_warehouse',
            'location_url',
        }
        self.assertEqual(expected_s3bucket_fields, set(response.data))

        apps3bucket = response.data['apps3buckets'][0]
        expected_apps3bucket_fields = {'id', 'url', 'app', 'access_level'}
        self.assertEqual(
            expected_apps3bucket_fields,
            set(apps3bucket)
        )

        expected_app_fields = {
            'id',
            'url',
            'name',
            'description',
            'slug',
            'repo_url',
            'iam_role_name',
            'created_by',
        }
        self.assertEqual(
            expected_app_fields,
            set(apps3bucket['app'])
        )

        users3bucket = response.data['users3buckets'][0]
        expected_users3bucket_fields = {
            'id',
            'user',
            'access_level',
            'is_admin'
        }
        self.assertEqual(
            expected_users3bucket_fields,
            set(users3bucket)
        )

        expected_user_fields = {
            'auth0_id',
            'url',
            'username',
            'name',
            'email',
        }
        self.assertEqual(
            expected_user_fields,
            set(users3bucket['user'])
        )

    def test_delete(self):
        response = self.client.delete(
            reverse('s3bucket-detail', (self.fixture.id,)))
        self.assertEqual(HTTP_204_NO_CONTENT, response.status_code)

        response = self.client.get(
            reverse('s3bucket-detail', (self.fixture.id,)))
        self.assertEqual(HTTP_404_NOT_FOUND, response.status_code)

    @patch('control_panel_api.models.S3Bucket.aws_create')
    def test_create(self, mock_aws_create):
        data = {'name': 'test-bucket-123'}
        response = self.client.post(reverse('s3bucket-list'), data)
        self.assertEqual(HTTP_201_CREATED, response.status_code)

        self.assertEqual(self.superuser.auth0_id, response.data['created_by'])
        self.assertFalse(response.data['is_data_warehouse'])

        mock_aws_create.assert_called()

        users3bucket = UserS3Bucket.objects.get(
            user_id=self.superuser.auth0_id,
            s3bucket_id=response.data['id'],
        )

        self.assertEqual(
            self.superuser.auth0_id, users3bucket.user.auth0_id)
        self.assertEqual(
            response.data['id'], users3bucket.s3bucket.id)
        self.assertEqual(
            UserS3Bucket.READWRITE, users3bucket.access_level)
        self.assertTrue(users3bucket.is_admin)

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

    def test_aws_error_existing_ignored(self):
        fixtures = (
            ('control_panel_api.aws.AWSClient.create_bucket',
             'BucketAlreadyOwnedByYou'),
        )

        for patch_func, aws_exception in fixtures:
            with patch(patch_func) as mock_call:
                e = type(aws_exception, (ClientError,), {})
                mock_call.side_effect = e({}, 'Foo')

                data = {'name': f'test-bucket-123-{aws_exception.lower()}'}
                response = self.client.post(reverse('s3bucket-list'), data)
                self.assertEqual(HTTP_201_CREATED, response.status_code)

                mock_call.assert_called()

    @patch('elasticsearch.Elasticsearch.search')
    def test_access_logs(self, mock_bucket_hits_aggregation):
        mock_bucket_hits_aggregation.return_value = BUCKET_HITS_AGGREGATION

        response = self.client.get(
            reverse('s3bucket-access-logs', (self.fixture.id,)))
        self.assertEqual(HTTP_200_OK, response.status_code)

        self.assertEqual(2, len(response.data))

        self.assertEqual('sentencing-policy-model',
                         response.data[0]['accessed_by'])
        self.assertEqual(11, response.data[0]['count'])
        self.assertEqual('app', response.data[0]['type'])

        self.assertEqual('foobar', response.data[1]['accessed_by'])
        self.assertEqual(3, response.data[1]['count'])
        self.assertEqual('user', response.data[1]['type'])


class UserS3BucketViewTest(AuthenticatedClientMixin, APITestCase):

    def setUp(self):
        super().setUp()
        self.user_1 = User.objects.create(
            auth0_id='github|1', username="user-1")
        self.user_2 = User.objects.create(
            auth0_id='github|2', username="user-2")
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

        expected_fields = {
            'id',
            'url',
            'user',
            's3bucket',
            'access_level',
            'is_admin'
        }
        self.assertEqual(
            expected_fields,
            set(response.data)
        )
        self.assertEqual('readonly', response.data['access_level'])

    @patch('control_panel_api.models.UserS3Bucket.aws_create')
    def test_create(self, mock_aws_create):
        data = {
            'user': self.user_2.auth0_id,
            's3bucket': self.s3_bucket_1.id,
            'access_level': AppS3Bucket.READONLY,
        }
        response = self.client.post(reverse('users3bucket-list'), data)
        self.assertEqual(HTTP_201_CREATED, response.status_code)

        mock_aws_create.assert_called()

    @patch('control_panel_api.models.services.revoke_bucket_access')
    def test_delete(self, mock_revoke_bucket_access):
        response = self.client.delete(
            reverse('users3bucket-detail', (self.users3bucket_1.id,)))
        self.assertEqual(HTTP_204_NO_CONTENT, response.status_code)

        mock_revoke_bucket_access.assert_called_with(
            self.users3bucket_1.s3bucket.arn,
            self.users3bucket_1.aws_role_name(),
        )

        response = self.client.get(
            reverse('users3bucket-detail', (self.users3bucket_1.id,)))
        self.assertEqual(HTTP_404_NOT_FOUND, response.status_code)

    @patch('control_panel_api.models.UserS3Bucket.aws_update')
    def test_update(self, mock_aws_update):
        data = {
            'user': self.user_1.auth0_id,
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
                'user': self.user_2.auth0_id,  # when app changed
                's3bucket': self.s3_bucket_1.id,
                'access_level': UserS3Bucket.READWRITE,
            },
            {
                'user': self.user_1.auth0_id,  # when s3bucket changed
                's3bucket': self.s3_bucket_2.id,
                'access_level': UserS3Bucket.READWRITE,
            },
        )

        for data in fixtures:
            response = self.client.put(
                reverse('users3bucket-detail', (self.users3bucket_1.id,)), data)
            self.assertEqual(HTTP_400_BAD_REQUEST, response.status_code)


class K8sAPIHandlerTest(AuthenticatedClientMixin, APITestCase):

    def setUp(self):
        super().setUp()
        self.K8S_HOST = 'https://k8s.local'
        self.K8S_AUTH_TOKEN = 'Basic test_token'
        self.K8S_SSL_CERT_PATH = '/path/to/ssl_ca_cert'
        self.USER_TOKEN = build_jwt_from_user(self.superuser)

    @patch('control_panel_api.authentication.get_jwks', mock_get_keys)
    @patch('control_panel_api.k8s.config')
    @patch('requests.request')
    def test_proxy(self, mock_request, mock_k8s_config):
        for (k8s_rbac_enabled, expected_auth) in [
            (False, self.K8S_AUTH_TOKEN),
            (True, f'Bearer {self.USER_TOKEN}'),
        ]:
            with override_settings(
                ENABLED={'k8s_rbac': k8s_rbac_enabled},
                OIDC_CLIENT_ID='audience',
            ):
                mock_k8s_config.host = self.K8S_HOST
                mock_k8s_config.ssl_ca_cert = self.K8S_SSL_CERT_PATH
                mock_k8s_config.authorization = self.K8S_AUTH_TOKEN

                TEST_DATA = b'{"test_pod": true}'
                mock_request.return_value.status_code = HTTP_201_CREATED
                mock_request.return_value.text = TEST_DATA

                K8S_PATH = '/api/v1/namespaces/user-alice/pods?foo=bar'
                response = self.client.post(
                    f'/k8s{K8S_PATH}',
                    TEST_DATA,
                    content_type='application/json',
                    HTTP_AUTHORIZATION=f'JWT {self.USER_TOKEN}',
                )

                self.assertEqual(HTTP_201_CREATED, response.status_code)
                self.assertEqual(TEST_DATA, response.content)
                mock_request.assert_called_with(
                    'post',
                    f'{self.K8S_HOST}{K8S_PATH}',
                    data=TEST_DATA,
                    headers={'authorization': expected_auth},
                    verify=self.K8S_SSL_CERT_PATH,
                )


class ToolDeploymentViewTest(AuthenticatedClientMixin, APITestCase):

    def setUp(self):
        super().setUp()
        self.normal_user = mommy.make('control_panel_api.User', is_superuser=False)
        self.client.force_login(self.normal_user)

    def test_create_when_invalid_tool_name(self):
        response = self.client.post(
            reverse('tool-deployments-list', ('unsupported-tool',)),
            None,
            content_type='application/json',
        )
        self.assertEqual(HTTP_400_BAD_REQUEST, response.status_code)

    @patch('control_panel_api.views.Tools', autospec=True)
    def test_create_when_valid_tool_name(self, mock_toolrepo):
        mock_tool_cls = mock_toolrepo.__getitem__.return_value
        mock_tool_instance = mock_tool_cls.return_value

        tool_name = 'rstudio'
        response = self.client.post(
            reverse('tool-deployments-list', (tool_name,)),
            None,
            content_type='application/json',
        )
        self.assertEqual(HTTP_201_CREATED, response.status_code)

        mock_toolrepo.__getitem__.assert_called_with(tool_name)
        mock_tool_instance.deploy_for.assert_called_with(self.normal_user)
