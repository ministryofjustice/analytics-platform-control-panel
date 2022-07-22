import pytest
from unittest import mock
from controlpanel.frontend import forms
from controlpanel.api.models import S3Bucket


def test_tool_release_form_check_release_name():
    """
    Ensure valid chart names work, while invalid ones cause a helpful
    exception.
    """
    data = {
        "name": "Test Release",
        "chart_name": "jupyter-lab",
        "version": "1.2.3",
        "values": {"foo": "bar"},
        "is_restricted": False,
        "target_infrastructure": "o",
    }
    f = forms.ToolReleaseForm(data)
    assert f.is_valid()
    data = {
        "name": "Test Release",
        "chart_name": "jupyter-lab-all-spark",
        "version": "1.2.3",
        "values": {"foo": "bar"},
        "is_restricted": False,
        "target_infrastructure": "o",
    }
    f = forms.ToolReleaseForm(data)
    assert f.is_valid()
    data = {
        "name": "Test Release",
        "chart_name": "rstudio",
        "version": "1.2.3",
        "values": {"foo": "bar"},
        "is_restricted": False,
        "target_infrastructure": "o",
    }
    f = forms.ToolReleaseForm(data)
    assert f.is_valid()
    data = {
        "name": "Test Release",
        "chart_name": "airflow-sqlite",
        "version": "1.2.3",
        "values": {"foo": "bar"},
        "is_restricted": False,
        "target_infrastructure": "o",
    }
    f = forms.ToolReleaseForm(data)
    assert f.is_valid()
    data = {
        "name": "Test Release",
        "chart_name": "invalid-chartname",
        "version": "1.2.3",
        "values": {"foo": "bar"},
        "is_restricted": False,
        "target_infrastructure": "o",
    }
    f = forms.ToolReleaseForm(data)
    assert f.is_valid() is False


def test_tool_release_form_check_tool_domain():
    """
    Ensure ONLY valid chart names work, while invalid ones cause a helpful
    exception.
    """
    data = {
        "name": "Test Release",
        "chart_name": "jupyter-lab",
        "version": "1.2.3",
        "values": {"foo": "bar"},
        "is_restricted": False,
        "target_infrastructure": "o",
        "tool_domain": "jupyter-lab",
    }
    f = forms.ToolReleaseForm(data)
    assert f.is_valid()
    data = {
        "name": "Test Release",
        "chart_name": "jupyter-lab-all-spark",
        "version": "1.2.3",
        "values": {"foo": "bar"},
        "is_restricted": False,
        "target_infrastructure": "o",
        "tool_domain": "jupyter-lab",
    }
    f = forms.ToolReleaseForm(data)
    assert f.is_valid()
    data = {
        "name": "Test Release",
        "chart_name": "jupyter-lab-all-spark",
        "version": "1.2.3",
        "values": {"foo": "bar"},
        "is_restricted": False,
        "target_infrastructure": "o",
        "tool_domain": "invalid-tool-domain",
    }
    f = forms.ToolReleaseForm(data)
    assert f.is_valid() is False


def test_tool_release_form_get_target_users():
    """
    Given a string list of comma separated usernames, the expected query to
    return the associated User objects is created.
    """
    f = forms.ToolReleaseForm()
    f.data = {
        "target_users_list": "aldo, nicholas, cal",
    }
    mock_user = mock.MagicMock()
    with mock.patch("controlpanel.frontend.forms.User", mock_user):
        f.get_target_users()
        mock_user.objects.filter.assert_called_once_with(
            username__in=set(["aldo", "nicholas", "cal"])
        )


def test_create_app_form_clean_new_datasource():
    """
    The CreateAppForm class has a bespoke "clean" method. We should ensure it
    checks the expected things in the correct way.
    """
    f = forms.CreateAppForm(
        data={
            "repo_url": "https://github.com/moj-analytical-services/my_repo",
            "connect_bucket": "new",
            "new_datasource_name": "test-bucketname",
            "connections": ["email"]
        }
    )
    f.clean_repo_url = mock.MagicMock()
    mock_s3 = mock.MagicMock()
    mock_s3.get.side_effect = S3Bucket.DoesNotExist("Boom")
    # A valid form returns True.
    with mock.patch("controlpanel.frontend.forms.S3Bucket.objects", mock_s3):
        assert f.is_valid() is True
    # A new datasource name is required if the connection is new.
    f = forms.CreateAppForm(
        data={
            "repo_url": "https://github.com/moj-analytical-services/my_repo",
            "connect_bucket": "new",
        }
    )
    f.clean_repo_url = mock.MagicMock()
    assert f.is_valid() is False
    assert "new_datasource_name" in f.errors
    # If a datasource already exists, report the duplication.
    f = forms.CreateAppForm(
        data={
            "repo_url": "https://github.com/moj-analytical-services/my_repo",
            "connect_bucket": "new",
            "new_datasource_name": "test-bucketname",
            "connections": ["email"]
        }
    )
    f.clean_repo_url = mock.MagicMock()
    mock_s3 = mock.MagicMock()
    with mock.patch("controlpanel.frontend.forms.S3Bucket.objects", mock_s3):
        assert f.is_valid() is False
        assert "new_datasource_name" in f.errors


def test_create_app_form_clean_existing_datasource():
    """
    An existing datasource name is required if the datasource is marked as
    already existing.
    """
    f = forms.CreateAppForm(
        data={
            "repo_url": "https://github.com/moj-analytical-services/my_repo",
            "connect_bucket": "existing",
            "connections": ["email"]
        }
    )
    f.clean_repo_url = mock.MagicMock()
    # A valid form returns True.
    assert f.is_valid() is False
    assert "existing_datasource_id" in f.errors


def test_create_app_form_clean_repo_url():
    """
    Ensure the various states of a GitHub repository result in a valid form or
    errors.
    """
    # The good case.
    f = forms.CreateAppForm(
        data={
            "repo_url": "https://github.com/moj-analytical-services/my_repo",
            "connect_bucket": "new",
            "new_datasource_name": "test-bucketname",
            "connections": ["email"]
        }
    )
    f.request = mock.MagicMock()
    mock_get_repo = mock.MagicMock(return_value=True)
    mock_app = mock.MagicMock()
    mock_app.objects.filter().exists.return_value = False
    mock_s3 = mock.MagicMock()
    mock_s3.get.side_effect = S3Bucket.DoesNotExist("Boom")
    with mock.patch(
        "controlpanel.frontend.forms.GithubAPI.get_repository", mock_get_repo
    ), mock.patch("controlpanel.frontend.forms.App", mock_app), mock.patch(
        "controlpanel.frontend.forms.S3Bucket.objects", mock_s3
    ):
        assert f.is_valid() is True
    # Repo not found.
    f = forms.CreateAppForm(
        data={
            "repo_url": "https://github.com/moj-analytical-services/my_repo",
            "connect_bucket": "new",
            "new_datasource_name": "test-bucketname",
        }
    )
    f.request = mock.MagicMock()
    mock_get_repo = mock.MagicMock(return_value=None)
    mock_app = mock.MagicMock()
    mock_app.objects.filter().exists.return_value = False
    mock_s3 = mock.MagicMock()
    mock_s3.get.side_effect = S3Bucket.DoesNotExist("Boom")
    with mock.patch(
        "controlpanel.frontend.forms.GithubAPI.get_repository", mock_get_repo
    ), mock.patch("controlpanel.frontend.forms.App", mock_app), mock.patch(
        "controlpanel.frontend.forms.S3Bucket.objects", mock_s3
    ):
        assert f.is_valid() is False
        assert "repo_url" in f.errors
    # App already exists.
    f = forms.CreateAppForm(
        data={
            "repo_url": "https://github.com/moj-analytical-services/my_repo",
            "connect_bucket": "new",
            "new_datasource_name": "test-bucketname",
        }
    )
    f.request = mock.MagicMock()
    mock_get_repo = mock.MagicMock(return_value=True)
    mock_app = mock.MagicMock()
    mock_app.objects.filter().exists.return_value = True
    mock_s3 = mock.MagicMock()
    mock_s3.get.side_effect = S3Bucket.DoesNotExist("Boom")
    with mock.patch(
        "controlpanel.frontend.forms.GithubAPI.get_repository", mock_get_repo
    ), mock.patch("controlpanel.frontend.forms.App", mock_app), mock.patch(
        "controlpanel.frontend.forms.S3Bucket.objects", mock_s3
    ):
        assert f.is_valid() is False
        assert "repo_url" in f.errors
