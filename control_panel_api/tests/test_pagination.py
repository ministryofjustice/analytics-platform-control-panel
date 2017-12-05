from model_mommy import mommy
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase

from control_panel_api.tests.test_views import AuthenticatedClientMixin


class TestPagination(AuthenticatedClientMixin, APITestCase):
    def test_pagination(self):
        mommy.make('control_panel_api.App', 120)  # 120 exceeds the 100 default

        app_list_url = reverse('app-list')

        fixtures = (
            (app_list_url, 100, True),  # default paging no query param
            (app_list_url + '?page_size=50', 50, True),  # less than default
            (app_list_url + '?page_size=130', 120, False),  # more than default
            (app_list_url + '?page_size=0', 120, False),  # return all
        )

        for url, expected_page_size, has_next in fixtures:
            response = self.client.get(url)
            self.assertEqual(120, response.data['count'])
            self.assertEqual(expected_page_size, len(response.data['results']))
            self.assertIsNone(response.data['previous'])
            if has_next:
                self.assertIsNotNone(response.data['next'])
            else:
                self.assertIsNone(response.data['next'])
