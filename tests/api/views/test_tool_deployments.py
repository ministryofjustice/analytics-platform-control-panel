from rest_framework import status
from rest_framework.reverse import reverse
from unittest.mock import patch


def test_get(client):
    response = client.get(reverse('tool-deployments', ('rstudio', 'deploy')))
    assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED


def test_post_not_valid_data(client):
    data = {'version': "rstudio_v1.0.0"}
    response = client.post(reverse('tool-deployments', ('rstudio', 'deploy')), data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_post_not_supported_action(client):
    data = {'version': "rstudio_v1.0.0"}
    response = client.post(reverse('tool-deployments', ('rstudio', 'testing')), data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_post(client):
    with patch('controlpanel.api.views.tool_deployments.start_background_task') as start_background_task:
        data = {'version': "rstudio__v1.0.0__1"}
        response = client.post(reverse('tool-deployments', ('rstudio', 'deploy')), data)
        start_background_task.assert_called()
        assert response.status_code == status.HTTP_200_OK
