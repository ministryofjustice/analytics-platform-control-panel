from unittest.mock import MagicMock, patch

from model_mommy import mommy
from rest_framework.reverse import reverse
from rest_framework.status import (
    HTTP_201_CREATED,
    HTTP_403_FORBIDDEN,
)
from rest_framework.test import APITestCase


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

    @patch('control_panel_api.views.Tools', MagicMock())
    def test_normal_user_can_deploy_tool(self):
        self.client.force_login(self.normal_user)

        response = self.client.post(
            reverse('tool-deployments-list', ('rstudio',)),
            None,
            content_type='application/json',
        )
        self.assertEqual(HTTP_201_CREATED, response.status_code)

    @patch('control_panel_api.views.Tools', MagicMock())
    def test_superuser_can_deploy_tool(self):
        self.client.force_login(self.superuser)

        response = self.client.post(
            reverse('tool-deployments-list', ('rstudio',)),
            None,
            content_type='application/json',
        )
        self.assertEqual(HTTP_201_CREATED, response.status_code)
