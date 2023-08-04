import pytest
from unittest.mock import patch

from model_mommy import mommy

from controlpanel.api.models import App
from controlpanel.api.tasks.handlers import create_app_aws_role


@pytest.mark.django_db
@patch("controlpanel.api.tasks.handlers.base.BaseModelTaskHandler.complete")
@patch("controlpanel.api.tasks.handlers.app.cluster")
def test_cluster_not_called_without_valid_app(cluster, complete, users):
    with pytest.raises(App.DoesNotExist):
        create_app_aws_role(1, users["superuser"].pk)
        cluster.App.assert_not_called()
        # should not be complete as we want to try it again
        complete.assert_not_called()


@pytest.mark.django_db
@patch("controlpanel.api.tasks.handlers.base.BaseModelTaskHandler.complete")
@patch("controlpanel.api.tasks.handlers.app.cluster")
def test_cluster_not_called_without_valid_user(cluster, complete, users):
    app = mommy.make("api.App")

    user = users["normal_user"]
    create_app_aws_role(app.pk, user.pk)

    # role should not be created
    cluster.App.assert_not_called()
    # task should be complete so that it does not run again, as user not valid
    complete.assert_called_once()


@pytest.mark.django_db
@patch("controlpanel.api.tasks.handlers.base.BaseModelTaskHandler.complete")
@patch("controlpanel.api.tasks.handlers.app.cluster")
def test_valid_app_and_user(cluster, complete, users):
    app = mommy.make("api.App")

    create_app_aws_role(app.pk, users["superuser"].pk)

    cluster.App.assert_called_once_with(app)
    cluster.App.return_value.create_iam_role.assert_called_once()
    complete.assert_called_once()
