# Standard library
from unittest.mock import PropertyMock, patch

# Third-party
import pytest
from model_bakery import baker

# First-party/Local
from controlpanel.api.models import App
from controlpanel.api.tasks.handlers import create_app_auth_settings


@pytest.mark.django_db
@patch("controlpanel.api.tasks.handlers.base.BaseModelTaskHandler.complete")
@patch("controlpanel.api.tasks.handlers.app.cluster")
def test_cluster_not_called_without_valid_app(cluster, complete, users):
    with pytest.raises(App.DoesNotExist):
        create_app_auth_settings(1, users["superuser"].pk)
        cluster.App.assert_not_called()
        # should not be complete as we want to try it again
        complete.assert_not_called()


@pytest.mark.django_db
@patch("controlpanel.api.tasks.handlers.base.BaseModelTaskHandler.complete")
@patch("controlpanel.api.tasks.handlers.app.cluster")
@patch(
    "controlpanel.api.models.user.User.github_api_token", new=PropertyMock(return_value=None)
)  # noqa
def test_cluster_not_called_without_github_api_token(cluster, complete, users):
    app = baker.make("api.App")

    user = users["superuser"]
    create_app_auth_settings(
        app.pk,
        user.pk,
        "envs",
        "disable_authentication",
        "connections",
    )

    # role should not be created
    cluster.App.assert_not_called()
    # task should be complete so that it does not run again, as user not valid
    complete.assert_called_once()


@pytest.mark.django_db
@patch("controlpanel.api.tasks.handlers.base.BaseModelTaskHandler.complete")
@patch("controlpanel.api.tasks.handlers.app.cluster")
@patch(
    "controlpanel.api.models.user.User.github_api_token",
    new=PropertyMock(return_value="dummy-token"),
)  # noqa
def test_valid_app_and_user(cluster, complete, users):
    app = baker.make("api.App")

    create_app_auth_settings(
        app.pk,
        users["superuser"].pk,
        ["test"],
        False,
        ["email"],
    )

    cluster.App.assert_called_once_with(app, "dummy-token")
    cluster.App.return_value.create_auth_settings.assert_called_once_with(
        env_name="test", disable_authentication=False, connections=["email"]
    )
    complete.assert_called_once()
