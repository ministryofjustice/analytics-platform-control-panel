from unittest.mock import patch

from model_mommy import mommy
import pytest
from rest_framework import status
from rest_framework.reverse import reverse


@pytest.yield_fixture
def ExtendedAuth0():
    with patch('controlpanel.api.auth0.ExtendedAuth0') as authz:
        yield authz.return_value


def test_delete(client, ExtendedAuth0):
    app = mommy.make('api.App')
    user_id = 'email|12345'

    response = client.delete(reverse('appcustomers-detail', (app.id, user_id)))

    assert response.status_code == status.HTTP_204_NO_CONTENT

    ExtendedAuth0.groups.delete_group_members.assert_called_with(
        group_name=app.slug,
        user_ids=[user_id],
    )
