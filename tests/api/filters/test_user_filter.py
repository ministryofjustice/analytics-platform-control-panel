from model_mommy import mommy
from rest_framework.reverse import reverse
from rest_framework.status import HTTP_200_OK
from rest_framework.test import APITestCase


class UserFilterTest(APITestCase):

    def setUp(self):
        self.superuser = mommy.make(
            "api.User", is_superuser=True)
        self.normal_user = mommy.make(
            "api.User", is_superuser=False)

    def test_superuser_sees_everything(self):
        self.client.force_login(self.superuser)

        response = self.client.get(reverse("user-list"))
        user_ids = [user["auth0_id"] for user in response.data["results"]]
        self.assertEqual(len(user_ids), 2)
        self.assertIn(self.superuser.auth0_id, user_ids)
        self.assertIn(self.normal_user.auth0_id, user_ids)

    def test_normal_user_sees_everything(self):
        self.client.force_login(self.normal_user)

        response = self.client.get(reverse("user-list"))
        self.assertEqual(HTTP_200_OK, response.status_code)
        self.assertEqual(len(response.data["results"]), 2)
