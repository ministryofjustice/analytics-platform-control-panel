from unittest.mock import MagicMock, patch

from model_mommy import mommy
from rest_framework.reverse import reverse
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_201_CREATED,
    HTTP_204_NO_CONTENT,
    HTTP_403_FORBIDDEN,
)
from rest_framework.test import APITestCase


@patch('control_panel_api.aws.aws.client', MagicMock())
@patch('control_panel_api.models.App.concourse_delete_pipeline', MagicMock())
@patch('control_panel_api.models.App.concourse_create_pipeline', MagicMock())
class AppPermissionsTest(APITestCase):
    def setUp(self):
        super().setUp()
        self.superuser = mommy.make(
            'control_panel_api.User', is_superuser=True)
        self.normal_user = mommy.make(
            'control_panel_api.User', is_superuser=False)

        self.app_1 = mommy.make(
            "control_panel_api.App", name="App 1")
        self.app_2 = mommy.make(
            "control_panel_api.App", name="App 2")

    def test_list_as_superuser_responds_OK(self):
        self.client.force_login(self.superuser)

        response = self.client.get(reverse('app-list'))
        self.assertEqual(HTTP_200_OK, response.status_code)

    def test_list_as_normal_user_responds_OK(self):
        self.client.force_login(self.normal_user)

        response = self.client.get(reverse('app-list'))
        self.assertEqual(HTTP_200_OK, response.status_code)

    def test_detail_as_superuser_responds_OK(self):
        self.client.force_login(self.superuser)

        response = self.client.get(reverse('app-detail', (self.app_1.id,)))
        self.assertEqual(HTTP_200_OK, response.status_code)

    def test_detail_as_normal_user_responds_403(self):
        self.client.force_login(self.normal_user)

        response = self.client.get(reverse('app-detail', (self.app_1.id,)))
        self.assertEqual(HTTP_403_FORBIDDEN, response.status_code)

    def test_delete_as_superuser_responds_OK(self):
        self.client.force_login(self.superuser)

        response = self.client.delete(
            reverse('app-detail', (self.app_1.id,)))
        self.assertEqual(HTTP_204_NO_CONTENT, response.status_code)

    def test_delete_as_normal_user_responds_403(self):
        self.client.force_login(self.normal_user)

        response = self.client.delete(
            reverse('app-detail', (self.app_1.id,)))
        self.assertEqual(HTTP_403_FORBIDDEN, response.status_code)

    def test_create_as_superuser_responds_OK(self):
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
