# Third-party
from model_mommy import mommy
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase


class AppFilterTest(APITestCase):
    def setUp(self):
        self.superuser = mommy.make("api.User", is_superuser=True)
        self.normal_user = mommy.make("api.User", is_superuser=False)

        self.app_1 = mommy.make("api.App", name="App 1")
        self.app_2 = mommy.make("api.App", name="App 2")

    def test_everyone_see_everything(self):
        for user in [self.superuser, self.normal_user]:
            self.client.force_login(user)

            response = self.client.get(reverse("app-list"))
            app_ids = [app["id"] for app in response.data["results"]]
            self.assertEqual(len(app_ids), 2)
            self.assertIn(self.app_1.id, app_ids)
            self.assertIn(self.app_2.id, app_ids)
