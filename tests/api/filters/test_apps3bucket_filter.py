from model_mommy import mommy
import pytest
from rest_framework import status
from rest_framework.reverse import reverse


NUM_APPS3BUCKETS = 2


@pytest.fixture(autouse=True)
def apps3buckets():
    mommy.make('api.AppS3Bucket', NUM_APPS3BUCKETS)


def list(client, *args):
    return client.get(reverse('apps3bucket-list'))


@pytest.mark.parametrize(
    'view,user,expected_length',
    [
        (list, 'superuser', NUM_APPS3BUCKETS),
        (list, 'normal_user', 0),
    ],
)
@pytest.mark.django_db
def test_filters(client, users, view, user, expected_length):
    client.force_login(users[user])
    response = view(client)
    assert len(response.data['results']) == expected_length

