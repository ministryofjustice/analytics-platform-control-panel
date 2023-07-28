import pytest
from unittest.mock import patch
from celery.exceptions import Retry
from model_mommy import mommy

from controlpanel.api.tasks import create_app_aws_role


@pytest.mark.django_db
@patch("controlpanel.api.tasks.create_app_aws_role.retry")
@patch("controlpanel.api.tasks.cluster")
def test_retry_when_app_does_not_exist(cluster, retry):
    retry.side_effect = Retry

    with pytest.raises(Retry):
        create_app_aws_role(app_pk=1)

    cluster.App.assert_not_called()


@pytest.mark.django_db
@patch("controlpanel.api.tasks.cluster")
def test_app_exists(cluster):
    app = mommy.make("api.App")

    create_app_aws_role(app_pk=app.pk)

    cluster.App.assert_called_once_with(app)
    cluster.App.return_value.create_iam_role.assert_called_once()
