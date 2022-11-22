from unittest.mock import patch

from model_mommy import mommy
import pytest
from rest_framework import status
from rest_framework.reverse import reverse


@pytest.fixture
def app():
    return mommy.make('api.App')


@pytest.yield_fixture
def ExtendedAuth0():
    with patch('controlpanel.api.models.app.auth0.ExtendedAuth0') as authz:
        yield authz.return_value


@pytest.yield_fixture
def fixture_users_200(ExtendedAuth0):
    with patch.object(ExtendedAuth0.users, "all") as request:
        request.side_effect = [
            {
                "total": 200,
                "users": [
                    {
                        "name": f"Test User {(i * 100) + j}",
                        "email": f"test{(i * 100) + j}@example.com",
                        "user_id": f"github|{(i * 100) + j}",
                        "extra_field": True
                    }
                    for j in range(100)
                ],
            }
            for i in range(2)
        ]
        yield


@pytest.yield_fixture
def fixture_group_mocked(ExtendedAuth0):
    with patch.object(ExtendedAuth0.groups, "get_group_id") as request:
        request.side_effect = 'my_group_id'
        yield request


@pytest.yield_fixture
def fixture_customers_mocked(ExtendedAuth0):
    with patch.object(ExtendedAuth0.groups, "get_group_members_paginated") as request:
        items = [
            {
                'total': 10,
                'users': [
                    {
                        "name": f"Test User {(i * 5) + j}",
                        "email": f"test{(i * 5) + j}@example.com",
                        "user_id": f"github|{(i * 5) + j}",
                    } for j in range(5)
                ]
            } for i in range(2)
        ]

        items.append([])

        request.side_effect = items
        yield request


def test_get(client, app, ExtendedAuth0):
    ExtendedAuth0.groups.get_group_members.return_value = [{
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


def test_post(client, app, ExtendedAuth0):
    emails = ['test1@example.com', 'test2@example.com']
    data = {'email': ', '.join(emails)}
    response = client.post(reverse('appcustomers-list', (app.id,)), data)
    assert response.status_code == status.HTTP_201_CREATED

    ExtendedAuth0.add_group_members_by_emails.assert_called_with(
        group_name=app.slug,
        emails=emails,
        user_options={'connection': 'email'},
    )


def test_get_paginated(client, app, ExtendedAuth0, fixture_customers_mocked):
    group_id = 1
    url_dict = {"group_id": group_id}

    response = client.get(reverse('appcustomers-page', args=(app.id,)), url_dict )
    fixture_customers_mocked.assert_called_with(str(group_id), page=1, per_page=25)

    first_users = response.json().get('results', [])
    assert len(first_users) == 5


def test_get_group_id(client, app, ExtendedAuth0, fixture_group_mocked):
    response = client.get(reverse('app-group-id', args=(app.id,)))
    assert response.json().get('group_id') == 'm'

