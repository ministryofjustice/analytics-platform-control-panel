from unittest.mock import MagicMock, patch

from model_mommy import mommy
from rest_framework.reverse import reverse
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_201_CREATED,
    HTTP_204_NO_CONTENT,
    HTTP_403_FORBIDDEN,
    HTTP_404_NOT_FOUND,
)
from rest_framework.test import APITestCase

from control_panel_api.aws import aws
from control_panel_api.helm import helm
from control_panel_api.models import AppS3Bucket


@patch.object(aws, 'client', MagicMock())
@patch.object(helm, '_helm_command', MagicMock())
class UserPermissionsTest(APITestCase):

    def setUp(self):
        super().setUp()
        self.superuser = mommy.make(
            'control_panel_api.User',
            auth0_id='github|user_1',
            is_superuser=True,
        )
        self.normal_user = mommy.make(
            'control_panel_api.User',
            auth0_id='github|user_2',
            is_superuser=False,
        )

    def test_list_as_superuser_responds_OK(self):
        self.client.force_login(self.superuser)

        response = self.client.get(reverse('user-list'))
        self.assertEqual(HTTP_200_OK, response.status_code)

    def test_list_as_normal_user_responds_403(self):
        self.client.force_login(self.normal_user)

        response = self.client.get(reverse('user-list'))
        self.assertEqual(HTTP_403_FORBIDDEN, response.status_code)

    def test_detail_as_superuser_responds_OK(self):
        self.client.force_login(self.superuser)

        response = self.client.get(
            reverse('user-detail', (self.normal_user.auth0_id,)))
        self.assertEqual(HTTP_200_OK, response.status_code)

    def test_own_detail_as_normal_user_responds_OK(self):
        self.client.force_login(self.normal_user)

        response = self.client.get(
            reverse('user-detail', (self.normal_user.auth0_id,)))
        self.assertEqual(HTTP_200_OK, response.status_code)

    def test_detail_as_normal_user_responds_404(self):
        self.client.force_login(self.normal_user)

        response = self.client.get(
            reverse('user-detail', (self.superuser.auth0_id,)))
        # 404 raised before object permissions checked
        self.assertEqual(HTTP_404_NOT_FOUND, response.status_code)

    def test_delete_as_superuser_responds_OK(self):
        self.client.force_login(self.superuser)

        response = self.client.delete(
            reverse('user-detail', (self.normal_user.auth0_id,)))
        self.assertEqual(HTTP_204_NO_CONTENT, response.status_code)

    def test_delete_as_normal_user_responds_403(self):
        self.client.force_login(self.normal_user)

        response = self.client.delete(
            reverse('user-detail', (self.normal_user.auth0_id,)))
        self.assertEqual(HTTP_403_FORBIDDEN, response.status_code)

    def test_create_as_superuser_responds_OK(self):
        self.client.force_login(self.superuser)

        data = {'username': 'foo', 'auth0_id': 'github|888'}
        response = self.client.post(reverse('user-list'), data)
        self.assertEqual(HTTP_201_CREATED, response.status_code)

    def test_create_as_normal_user_responds_403(self):
        self.client.force_login(self.normal_user)

        data = {'username': 'foo'}
        response = self.client.post(reverse('user-list'), data)
        self.assertEqual(HTTP_403_FORBIDDEN, response.status_code)

    def test_update_as_superuser_responds_OK(self):
        self.client.force_login(self.superuser)

        data = {'username': 'foo', 'auth0_id': 'github|888'}
        response = self.client.put(
            reverse('user-detail', (self.normal_user.auth0_id,)), data)
        self.assertEqual(HTTP_200_OK, response.status_code)

    def test_update_self_as_normal_user_responds_OK(self):
        self.client.force_login(self.normal_user)

        data = {'username': 'foo', 'auth0_id': 'github|888'}
        response = self.client.put(
            reverse('user-detail', (self.normal_user.auth0_id,)), data)
        self.assertEqual(HTTP_200_OK, response.status_code)

    def test_update_as_normal_user_responds_404(self):
        self.client.force_login(self.normal_user)

        data = {'username': 'foo', 'auth0_id': 'github|888'}
        response = self.client.put(
            reverse('user-detail', (self.superuser.auth0_id,)), data)
        # 404 raised before object permissions checked
        self.assertEqual(HTTP_404_NOT_FOUND, response.status_code)


@patch.object(aws, 'client', MagicMock())
class AppPermissionsTest(APITestCase):

    def setUp(self):
        super().setUp()
        # Create users
        self.superuser = mommy.make(
            'control_panel_api.User', is_superuser=True)
        self.normal_user = mommy.make(
            'control_panel_api.User', is_superuser=False)
        # Create some apps
        self.app_1 = mommy.make(
            "control_panel_api.App", name="App 1")
        self.app_2 = mommy.make(
            "control_panel_api.App", name="App 2")

    def test_list_as_superuser_responds_OK(self):
        self.client.force_login(self.superuser)

        response = self.client.get(reverse('app-list'))
        self.assertEqual(HTTP_200_OK, response.status_code)

    def test_list_as_normal_user_responds_403(self):
        self.client.force_login(self.normal_user)

        response = self.client.get(reverse('app-list'))
        self.assertEqual(HTTP_403_FORBIDDEN, response.status_code)

    def test_detail_as_superuser_responds_OK(self):
        self.client.force_login(self.superuser)

        response = self.client.get(reverse('app-detail', (self.app_1.id,)))
        self.assertEqual(HTTP_200_OK, response.status_code)

    def test_detail_as_normal_user_responds_403(self):
        self.client.force_login(self.normal_user)

        response = self.client.get(reverse('app-detail', (self.app_1.id,)))
        self.assertEqual(HTTP_403_FORBIDDEN, response.status_code)

    @patch('boto3.client')
    def test_delete_as_superuser_responds_OK(self, mock_client):
        self.client.force_login(self.superuser)

        response = self.client.delete(
            reverse('app-detail', (self.app_1.id,)))
        self.assertEqual(HTTP_204_NO_CONTENT, response.status_code)

    def test_delete_as_normal_user_responds_403(self):
        self.client.force_login(self.normal_user)

        response = self.client.delete(
            reverse('app-detail', (self.app_1.id,)))
        self.assertEqual(HTTP_403_FORBIDDEN, response.status_code)

    @patch('boto3.client')
    def test_create_as_superuser_responds_OK(self, mock_client):
        self.client.force_login(self.superuser)

        data = {'name': 'foo', 'repo_url': 'https://example.com'}
        response = self.client.post(reverse('app-list'), data)
        self.assertEqual(HTTP_201_CREATED, response.status_code)

    def test_create_as_normal_user_responds_403(self):
        self.client.force_login(self.normal_user)

        data = {'name': 'foo'}
        response = self.client.post(reverse('app-list'), data)
        self.assertEqual(HTTP_403_FORBIDDEN, response.status_code)

    def test_update_as_superuser_responds_OK(self):
        self.client.force_login(self.superuser)

        data = {'name': 'foo', 'repo_url': 'http://foo.com'}
        response = self.client.put(
            reverse('app-detail', (self.app_1.id,)), data)
        self.assertEqual(HTTP_200_OK, response.status_code)

    def test_update_as_normal_user_responds_403(self):
        self.client.force_login(self.normal_user)

        data = {'name': 'foo', 'repo_url': 'http://foo.com'}
        response = self.client.put(
            reverse('app-detail', (self.app_1.id,)), data)
        self.assertEqual(HTTP_403_FORBIDDEN, response.status_code)


@patch.object(aws, 'client', MagicMock())
class AppS3BucketPermissionsTest(APITestCase):

    def setUp(self):
        super().setUp()
        # Create users
        self.superuser = mommy.make(
            "control_panel_api.User", is_superuser=True)
        self.normal_user = mommy.make(
            "control_panel_api.User", is_superuser=False)
        # Create some apps
        self.app_1 = mommy.make(
            "control_panel_api.App", name="App 1")
        self.app_2 = mommy.make(
            "control_panel_api.App", name="App 2")
        # Create some S3 buckets
        self.s3bucket_1 = mommy.make(
            "control_panel_api.S3Bucket", name="test-bucket-1")
        self.s3bucket_2 = mommy.make(
            "control_panel_api.S3Bucket", name="test-bucket-2")
        self.s3bucket_3 = mommy.make(
            "control_panel_api.S3Bucket", name="test-bucket-3")
        # Grant access to these S3 buckets
        self.apps3bucket_1 = self.app_1.apps3buckets.create(
            s3bucket=self.s3bucket_1,
            access_level=AppS3Bucket.READONLY,
        )
        self.apps3bucket_2 = self.app_2.apps3buckets.create(
            s3bucket=self.s3bucket_2,
            access_level=AppS3Bucket.READONLY,
        )

    def test_list_as_superuser_responds_OK(self):
        self.client.force_login(self.superuser)

        response = self.client.get(reverse('apps3bucket-list'))
        self.assertEqual(HTTP_200_OK, response.status_code)

    def test_list_as_normal_user_responds_403(self):
        self.client.force_login(self.normal_user)

        response = self.client.get(reverse('apps3bucket-list'))
        self.assertEqual(HTTP_403_FORBIDDEN, response.status_code)

    def test_detail_as_superuser_responds_OK(self):
        self.client.force_login(self.superuser)

        response = self.client.get(
            reverse('apps3bucket-detail', (self.apps3bucket_1.id,)))
        self.assertEqual(HTTP_200_OK, response.status_code)

    def test_detail_as_normal_user_responds_403(self):
        self.client.force_login(self.normal_user)

        response = self.client.get(
            reverse('apps3bucket-detail', (self.apps3bucket_1.id,)))
        self.assertEqual(HTTP_403_FORBIDDEN, response.status_code)

    def test_delete_as_superuser_responds_OK(self):
        self.client.force_login(self.superuser)

        response = self.client.delete(
            reverse('apps3bucket-detail', (self.apps3bucket_1.id,)))
        self.assertEqual(HTTP_204_NO_CONTENT, response.status_code)

    def test_delete_as_normal_user_responds_403(self):
        self.client.force_login(self.normal_user)

        response = self.client.delete(
            reverse('apps3bucket-detail', (self.apps3bucket_1.id,)))
        self.assertEqual(HTTP_403_FORBIDDEN, response.status_code)

    def test_create_as_superuser_responds_OK(self):
        self.client.force_login(self.superuser)

        data = {
            'app': self.app_1.id,
            's3bucket': self.s3bucket_3.id,
            'access_level': AppS3Bucket.READWRITE,
        }
        response = self.client.post(reverse('apps3bucket-list'), data)
        self.assertEqual(HTTP_201_CREATED, response.status_code)

    def test_create_as_normal_user_responds_403(self):
        self.client.force_login(self.normal_user)

        data = {'doesnt': 'matter'}
        response = self.client.post(reverse('apps3bucket-list'), data)
        self.assertEqual(HTTP_403_FORBIDDEN, response.status_code)

    def test_update_as_superuser_responds_OK(self):
        self.client.force_login(self.superuser)

        data = {
            'app': self.app_1.id,
            's3bucket': self.s3bucket_1.id,
            'access_level': AppS3Bucket.READWRITE,
        }
        response = self.client.put(
            reverse('apps3bucket-detail', (self.apps3bucket_1.id,)), data)
        self.assertEqual(HTTP_200_OK, response.status_code)

    def test_update_as_normal_user_responds_403(self):
        self.client.force_login(self.normal_user)

        data = {'doesnt': 'matter'}
        response = self.client.put(
            reverse('apps3bucket-detail', (self.apps3bucket_1.id,)), data)
        self.assertEqual(HTTP_403_FORBIDDEN, response.status_code)


@patch.object(aws, 'client', MagicMock())
class S3BucketPermissionsTest(APITestCase):

    def setUp(self):
        super().setUp()
        # Create users
        self.superuser = mommy.make(
            'control_panel_api.User', is_superuser=True)
        self.normal_user = mommy.make(
            'control_panel_api.User', is_superuser=False)
        # Create some S3 buckets
        self.s3bucket_1 = mommy.make(
            "control_panel_api.S3Bucket", name="test-bucket-1")
        self.s3bucket_2 = mommy.make(
            "control_panel_api.S3Bucket", name="test-bucket-2")

    def test_list_as_superuser_responds_OK(self):
        self.client.force_login(self.superuser)

        response = self.client.get(reverse('s3bucket-list'))
        self.assertEqual(HTTP_200_OK, response.status_code)

    def test_list_as_normal_user_responds_403(self):
        self.client.force_login(self.normal_user)

        response = self.client.get(reverse('s3bucket-list'))
        self.assertEqual(HTTP_403_FORBIDDEN, response.status_code)

    def test_detail_as_superuser_responds_OK(self):
        self.client.force_login(self.superuser)

        response = self.client.get(
            reverse('s3bucket-detail', (self.s3bucket_1.id,)))
        self.assertEqual(HTTP_200_OK, response.status_code)

    def test_detail_as_normal_user_responds_403(self):
        self.client.force_login(self.normal_user)

        response = self.client.get(
            reverse('s3bucket-detail', (self.s3bucket_1.id,)))
        self.assertEqual(HTTP_403_FORBIDDEN, response.status_code)

    def test_delete_as_superuser_responds_OK(self):
        self.client.force_login(self.superuser)

        response = self.client.delete(
            reverse('s3bucket-detail', (self.s3bucket_1.id,)))
        self.assertEqual(HTTP_204_NO_CONTENT, response.status_code)

    def test_delete_as_normal_user_responds_403(self):
        self.client.force_login(self.normal_user)

        response = self.client.delete(
            reverse('s3bucket-detail', (self.s3bucket_1.id,)))
        self.assertEqual(HTTP_403_FORBIDDEN, response.status_code)

    def test_create_as_superuser_responds_OK(self):
        self.client.force_login(self.superuser)

        data = {'name': 'test-bucket'}
        response = self.client.post(reverse('s3bucket-list'), data)
        self.assertEqual(HTTP_201_CREATED, response.status_code)

    def test_create_as_normal_user_responds_403(self):
        self.client.force_login(self.normal_user)

        data = {'name': 'test-bucket'}
        response = self.client.post(reverse('s3bucket-list'), data)
        self.assertEqual(HTTP_403_FORBIDDEN, response.status_code)

    def test_update_as_superuser_responds_OK(self):
        self.client.force_login(self.superuser)

        data = {'name': 'test-bucket-updated'}
        response = self.client.put(
            reverse('s3bucket-detail', (self.s3bucket_1.id,)), data)
        self.assertEqual(HTTP_200_OK, response.status_code)

    def test_update_as_normal_user_responds_403(self):
        self.client.force_login(self.normal_user)

        data = {'name': 'test-bucket-updated'}
        response = self.client.put(
            reverse('s3bucket-detail', (self.s3bucket_1.id,)), data)
        self.assertEqual(HTTP_403_FORBIDDEN, response.status_code)


class K8sPermissionsTest(APITestCase):

    def setUp(self):
        super().setUp()
        self.superuser = mommy.make(
            'control_panel_api.User',
            auth0_id='github|user_1',
            is_superuser=True,
        )
        self.normal_user = mommy.make(
            'control_panel_api.User',
            username='alice',
            auth0_id='github|user_2',
            is_superuser=False,
        )

    def test_when_not_authenticated_responds_403(self):
        response = self.client.get('/k8s/something')
        self.assertEqual(HTTP_403_FORBIDDEN, response.status_code)

    @patch('kubernetes.client.configuration')
    @patch('kubernetes.config.load_incluster_config')
    @patch('requests.request')
    def test_superuser_can_do_anything(self, mock_request, mock_load_config, mock_config):
        self.client.force_login(self.superuser)

        mock_request.return_value.status_code = 200

        response = self.client.get('/k8s/anything')
        self.assertEqual(HTTP_200_OK, response.status_code)

    def test_normal_user_cant_operate_outside_their_namespace(self):
        self.client.force_login(self.normal_user)

        response = self.client.get('/k8s/api/v1/namespaces/user-other/')
        self.assertEqual(HTTP_403_FORBIDDEN, response.status_code)

    @patch('kubernetes.client.configuration')
    @patch('kubernetes.config.load_incluster_config')
    @patch('requests.request')
    def test_normal_user_can_operate_in_their_namespace(self, mock_request, mock_load_config, mock_config):
        self.client.force_login(self.normal_user)

        mock_request.return_value.status_code = 200

        username = self.normal_user.username.lower()

        api_groups = [
            'api/v1',
            'apis/apps/v1beta2',
        ]

        for api in api_groups:
            response = self.client.get(f'/k8s/{api}/namespaces/user-{username}/')
            self.assertEqual(HTTP_200_OK, response.status_code)

    def test_normal_user_cant_make_requests_to_disallowed_apis(self):
        self.client.force_login(self.normal_user)

        username = self.normal_user.username.lower()

        disallowed_api = 'apis/disallowed/v1alpha0'
        response = self.client.get(f'/k8s/{disallowed_api}/namespaces/user-{username}/')
        self.assertEqual(HTTP_403_FORBIDDEN, response.status_code)

    def test_normal_user_cant_operate_on_namespaces_with_same_prefix(self):
        self.client.force_login(self.normal_user)

        username = self.normal_user.username.lower()
        other_username = f'{username}other'

        response = self.client.get(f'/k8s/api/v1/namespaces/user-{other_username}/do/something')
        self.assertEqual(HTTP_403_FORBIDDEN, response.status_code)


class ToolDeploymentPermissionsTest(APITestCase):

    def setUp(self):
        super().setUp()
        self.superuser = mommy.make(
            'control_panel_api.User',
            auth0_id='github|user_1',
            is_superuser=True,
        )
        self.normal_user = mommy.make(
            'control_panel_api.User',
            username='alice',
            auth0_id='github|user_2',
            is_superuser=False,
        )

    def test_not_logged_user_cant_deploy(self):
        response = self.client.post(
            reverse('tool-deployments-list', ('rstudio',)),
            None,
            content_type='application/json',
        )
        self.assertEqual(HTTP_403_FORBIDDEN, response.status_code)

    @patch('control_panel_api.views.Tool')
    def test_normal_user_can_deploy_tool(self, mock_tool):
        self.client.force_login(self.normal_user)

        response = self.client.post(
            reverse('tool-deployments-list', ('rstudio',)),
            None,
            content_type='application/json',
        )
        self.assertEqual(HTTP_201_CREATED, response.status_code)

    @patch('control_panel_api.views.Tool')
    def test_superuser_can_deploy_tool(self, mock_tool):
        self.client.force_login(self.superuser)

        response = self.client.post(
            reverse('tool-deployments-list', ('rstudio',)),
            None,
            content_type='application/json',
        )
        self.assertEqual(HTTP_201_CREATED, response.status_code)
