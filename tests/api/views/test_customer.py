from unittest.mock import patch

from model_mommy import mommy
import pytest
from rest_framework import status
from rest_framework.reverse import reverse


@pytest.fixture
def app():
    return mommy.make('api.App')


@pytest.yield_fixture
def AuthorizationAPI():
    with patch('controlpanel.api.models.app.auth0.AuthorizationAPI') as authz:
        yield authz.return_value


def test_get(client, app, AuthorizationAPI):
    AuthorizationAPI.get_group_members.return_value = [{
        "email": "a.user@digital.justice.gov.uk",
        "user_id": "email|5955f7ee86da0c1d55foobar",
        "nickname": "a.user",
        "name": "a.user@digital.justice.gov.uk",
        "foo": "bar",
        "baz": "bat",
    }]

    response = client.get(reverse('appcustomers-list', (app.id,)))

    assert response.status_code == status.HTTP_200_OK
    assert len(response.data) == 1

    expected_fields = {
        'email',
        'user_id',
        'nickname',
        'name',
    }
    assert set(response.data[0]) == expected_fields


def test_post(client, app, AuthorizationAPI):
    emails = ['test1@example.com', 'test2@example.com']
    data = {'email': ', '.join(emails)}
    response = client.post(reverse('appcustomers-list', (app.id,)), data)
    assert response.status_code == status.HTTP_201_CREATED

    AuthorizationAPI.add_group_members.assert_called_with(
        group_name=app.slug,
        emails=emails,
        user_options={'connection': 'email'},
    )
