from model_mommy import mommy
from rest_framework.reverse import reverse
from rest_framework.status import HTTP_403_FORBIDDEN
from rest_framework.test import APITestCase


class AppFilterTest(APITestCase):

    def setUp(self):
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

    def test_superuser_sees_everything(self):
        self.client.force_login(self.superuser)

        response = self.client.get(reverse("app-list"))
        app_ids = [app["id"] for app in response.data["results"]]
        self.assertEqual(len(app_ids), 2)
        self.assertIn(self.app_1.id, app_ids)
        self.assertIn(self.app_2.id, app_ids)

    def test_normal_user_sees_nothing(self):
        self.client.force_login(self.normal_user)

        response = self.client.get(reverse("app-list"))
        self.assertEqual(HTTP_403_FORBIDDEN, response.status_code)


class UserFilterTest(APITestCase):

    def setUp(self):
        self.superuser = mommy.make(
            "control_panel_api.User", is_superuser=True)
        self.normal_user = mommy.make(
            "control_panel_api.User", is_superuser=False)

    def test_superuser_sees_everything(self):
        self.client.force_login(self.superuser)

        response = self.client.get(reverse("user-list"))
        user_ids = [user["id"] for user in response.data["results"]]
        self.assertEqual(len(user_ids), 2)
        self.assertIn(self.superuser.id, user_ids)
        self.assertIn(self.normal_user.id, user_ids)

    def test_normal_user_sees_nothing(self):
        self.client.force_login(self.normal_user)

        response = self.client.get(reverse("user-list"))
        self.assertEqual(HTTP_403_FORBIDDEN, response.status_code)
