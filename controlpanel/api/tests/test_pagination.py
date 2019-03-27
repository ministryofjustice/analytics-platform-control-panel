from model_mommy import mommy
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase

from control_panel_api.tests.test_views import AuthenticatedClientMixin


class TestPagination(AuthenticatedClientMixin, APITestCase):
    def test_pagination(self):
        default_page_size = 100

        mommy.make('control_panel_api.App', default_page_size + 20)

        app_list_url = reverse('app-list')

        fixtures = (
            (app_list_url, default_page_size, True, False),
            (f'{app_list_url}?page_size={default_page_size - 50}', 50, True, False),
            (f'{app_list_url}?page_size={default_page_size - 50}&page=3', 20, False, True),
            (f'{app_list_url}?page_size={default_page_size + 30}', 120, False, False),
            (f'{app_list_url}?page_size=0', 120, False, False),
        )

        for url, expected_page_size, has_next, has_prev in fixtures:
            response = self.client.get(url)
            self.assertEqual(120, response.data['count'])
            self.assertEqual(expected_page_size, len(response.data['results']))

            if has_next:
                self.assertIsNotNone(response.data['next'])
            else:
                self.assertIsNone(response.data['next'])

            if has_prev:
                self.assertIsNotNone(response.data['previous'])
            else:
                self.assertIsNone(response.data['previous'])
