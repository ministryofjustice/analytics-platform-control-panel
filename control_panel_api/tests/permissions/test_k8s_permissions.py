from unittest.mock import MagicMock, patch

from model_mommy import mommy
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_403_FORBIDDEN,
)
from rest_framework.test import APITestCase


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

    @patch('kubernetes.client.configuration', MagicMock())
    @patch('kubernetes.config.load_incluster_config', MagicMock())
    @patch('requests.request')
    def test_superuser_can_do_anything(self, mock_request):
        self.client.force_login(self.superuser)

        mock_request.return_value.status_code = 200

        response = self.client.get('/k8s/anything')
        self.assertEqual(HTTP_200_OK, response.status_code)

    def test_normal_user_cant_operate_outside_their_namespace(self):
        self.client.force_login(self.normal_user)

        response = self.client.get('/k8s/api/v1/namespaces/user-other/')
        self.assertEqual(HTTP_403_FORBIDDEN, response.status_code)

    @patch('kubernetes.client.configuration', MagicMock())
    @patch('kubernetes.config.load_incluster_config', MagicMock())
    @patch('requests.request')
    def test_normal_user_can_operate_in_their_namespace(self, mock_request):
        self.client.force_login(self.normal_user)

        mock_request.return_value.status_code = 200

        username = self.normal_user.username.lower()

        api_groups = [
            'api/v1',
            'apis/apps/v1beta2',
        ]

        for api in api_groups:
            response = self.client.get(
                f'/k8s/{api}/namespaces/user-{username}/')
            self.assertEqual(HTTP_200_OK, response.status_code)

    def test_normal_user_cant_make_requests_to_disallowed_apis(self):
        self.client.force_login(self.normal_user)

        username = self.normal_user.username.lower()

        disallowed_api = 'apis/disallowed/v1alpha0'
        response = self.client.get(
            f'/k8s/{disallowed_api}/namespaces/user-{username}/')
        self.assertEqual(HTTP_403_FORBIDDEN, response.status_code)

    def test_normal_user_cant_operate_on_namespaces_with_same_prefix(self):
        self.client.force_login(self.normal_user)

        username = self.normal_user.username.lower()
        other_username = f'{username}other'

        response = self.client.get(
            f'/k8s/api/v1/namespaces/user-{other_username}/do/something')
        self.assertEqual(HTTP_403_FORBIDDEN, response.status_code)
