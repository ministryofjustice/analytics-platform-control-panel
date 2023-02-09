# Third-party
from model_mommy import mommy
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase


class AppFilterTest(APITestCase):
    def setUp(self):
        self.superuser = mommy.make("api.User", is_superuser=True)
        self.app_admin = mommy.make("api.User", is_superuser=False)
        self.app_1 = mommy.make("api.App", name="App 1")
        self.app_2 = mommy.make("api.App", name="App 2")
        mommy.make("api.UserApp", user=self.app_admin, app=self.app_1, is_admin=True)
        mommy.make("api.UserApp", user=self.app_admin, app=self.app_2, is_admin=True)

    def test_everyone_see_everything(self):
        for user in [self.superuser, self.app_admin]:
            self.client.force_login(user)

            response = self.client.get(reverse("app-list"))
            app_res_ids = [app["res_id"] for app in response.data["results"]]
            self.assertEqual(len(app_res_ids), 2)
            self.assertIn(str(self.app_1.res_id), app_res_ids)
            self.assertIn(str(self.app_2.res_id), app_res_ids)
