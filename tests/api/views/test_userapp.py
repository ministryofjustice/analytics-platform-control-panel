import json

from model_mommy import mommy
import pytest
from rest_framework import status
from rest_framework.reverse import reverse

from controlpanel.api.models import UserApp


@pytest.fixture
def apps():
    return {
        1: mommy.make('api.App', name='app_1'),
        2: mommy.make('api.App', name='app_2'),
    }


@pytest.fixture
def userapps(apps, users):
    return {
        1: UserApp.objects.create(
            user=users["superuser"],
            app=apps[1],
            is_admin=True,
        ),
        2: UserApp.objects.create(
            user=users['normal_user'],
            app=apps[1],
            is_admin=True,
        ),
    }


def test_list(client, userapps):
    response = client.get(reverse('userapp-list'))
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data['results']) == 2


def test_detail(client, userapps):
    response = client.get(reverse('userapp-detail', (userapps[1].id,)))
    assert response.status_code == status.HTTP_200_OK

    expected_fields = {'id', 'url', 'app', 'user', 'is_admin'}
    assert set(response.data) == expected_fields

    assert response.data['is_admin']


def test_create(client, apps, users):
    data = {
        'app': apps[2].id,
        'user': users['normal_user'].auth0_id,
        'is_admin': False,
    }
    response = client.post(reverse('userapp-list'), data)
    assert response.status_code == status.HTTP_201_CREATED


def test_update(client, apps, users, userapps):
    data = {
        'app': apps[1].id,
        'user': users['normal_user'].auth0_id,
        'is_admin': False,
    }
    response = client.put(
        reverse('userapp-detail', (userapps[2].id,)),
        json.dumps(data),
        content_type="application/json",
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.data['is_admin'] == data['is_admin']


def test_delete(client, userapps):
    response = client.delete(reverse('userapp-detail', (userapps[2].id,)))
    assert response.status_code == status.HTTP_204_NO_CONTENT

    response = client.get(reverse('userapp-detail', (userapps[2].id,)))
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.parametrize(
    "app, user, is_admin",
    [
        (2, "normal_user", True),
        (1, "superuser", True),
    ],
    ids=[
        'app-changed',
        'user-changed',
    ],
)
def test_update_bad_requests(client, apps, users, userapps, app, user, is_admin):
    response = client.put(
        reverse('userapp-detail', (userapps[2].id,)),
        json.dumps({
            "app": apps[app].id,
            "user": users[user].auth0_id,
            "is_admin": is_admin,
        }),
        content_type="application/json",
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
