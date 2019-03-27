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
@patch('control_panel_api.helm.helm._helm_command', MagicMock())
@patch('control_panel_api.helm.helm._helm_shell_command', MagicMock())
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

    def test_list_as_normal_user_responds_OK(self):
        self.client.force_login(self.normal_user)

        response = self.client.get(reverse('user-list'))
        self.assertEqual(HTTP_200_OK, response.status_code)

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

    def test_detail_as_normal_user_responds_403(self):
        self.client.force_login(self.normal_user)

        response = self.client.get(
            reverse('user-detail', (self.superuser.auth0_id,)))
        self.assertEqual(HTTP_403_FORBIDDEN, response.status_code)

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

    def test_update_as_normal_user_responds_403(self):
        self.client.force_login(self.normal_user)

        data = {'username': 'foo', 'auth0_id': 'github|888'}
        response = self.client.put(
            reverse('user-detail', (self.superuser.auth0_id,)), data)
        self.assertEqual(HTTP_403_FORBIDDEN, response.status_code)

