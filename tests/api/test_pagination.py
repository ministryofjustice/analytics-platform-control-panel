from model_mommy import mommy
import pytest
from rest_framework.reverse import reverse


DEFAULT_PAGE_SIZE = 100


@pytest.fixture(autouse=True)
def login_superuser(client, superuser):
    client.force_login(superuser)


@pytest.mark.parametrize(
    "urlparams, page_size, next, prev",
    [
        ({}, DEFAULT_PAGE_SIZE, True, False),
        ({'page_size': DEFAULT_PAGE_SIZE - 50}, 50, True, False),
        ({'page_size': DEFAULT_PAGE_SIZE - 50, 'page': 3}, 20, False, True),
        ({'page_size': DEFAULT_PAGE_SIZE + 30}, 120, False, False),
        ({'page_size': 0}, 120, False, False),
    ],
)
@pytest.mark.django_db
def test_pagination(client, urlparams, page_size, next, prev):
    mommy.make('api.App', DEFAULT_PAGE_SIZE + 20)
    app_list_url = reverse('app-list')

    response = client.get(app_list_url, urlparams)
    assert response.data['count'] == 120
    assert len(response.data['results']) == page_size

    assert (response.data.get('next') is not None) == next
    assert (response.data.get('previous') is not None) == prev
