from rest_framework import status
from rest_framework.reverse import reverse


def user_list(client):
    return client.get(reverse('user-list'))


def test_superuser_sees_everything(client, users):
    client.force_login(users['superuser'])
    response = user_list(client)
    assert response.status_code == status.HTTP_200_OK

    all_user_ids = [user.auth0_id for key, user in users.items()]
    returned_user_ids = [user["auth0_id"] for user in response.data["results"]]

    assert set(returned_user_ids) == set(all_user_ids)


def test_normal_user_sees_nothing(client, users):
    client.force_login(users['normal_user'])
    response = user_list(client)
    assert response.status_code == status.HTTP_403_FORBIDDEN
