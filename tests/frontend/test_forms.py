# Standard library
from unittest import mock

# Third-party
import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse


# First-party/Local
from controlpanel.api import aws
from controlpanel.api.github import RepositoryNotFound
from controlpanel.api.models import S3Bucket
from controlpanel.frontend import forms


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
    }
    f = forms.ToolReleaseForm(data)
    assert f.is_valid()
    data = {
        "name": "Test Release",
        "chart_name": "jupyter-lab-all-spark",
        "version": "1.2.3",
        "values": {"foo": "bar"},
        "is_restricted": False,
    }
    f = forms.ToolReleaseForm(data)
    assert f.is_valid()
    data = {
        "name": "Test Release",
        "chart_name": "rstudio",
        "version": "1.2.3",
        "values": {"foo": "bar"},
        "is_restricted": False,
    }
    f = forms.ToolReleaseForm(data)
    assert f.is_valid()
    data = {
        "name": "Test Release",
        "chart_name": "airflow-sqlite",
        "version": "1.2.3",
        "values": {"foo": "bar"},
        "is_restricted": False,
    }
    f = forms.ToolReleaseForm(data)
    assert f.is_valid()
    data = {
        "name": "Test Release",
        "chart_name": "visual-studio-code",
        "version": "1.2.3",
        "values": {"foo": "bar"},
        "is_restricted": False,
    }
    f = forms.ToolReleaseForm(data)
    assert f.is_valid()
    data = {
        "name": "Test Release",
        "chart_name": "invalid-chartname",
        "version": "1.2.3",
        "values": {"foo": "bar"},
        "is_restricted": False,
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
        "tool_domain": "jupyter-lab",
    }
    f = forms.ToolReleaseForm(data)
    assert f.is_valid()
    data = {
        "name": "Test Release",
        "chart_name": "visual-studio-code",
        "version": "1.2.3",
        "values": {"foo": "bar"},
        "is_restricted": False,
        "tool_domain": "vscode",
    }
    f = forms.ToolReleaseForm(data)
    assert f.is_valid()
    data = {
        "name": "Test Release",
        "chart_name": "jupyter-lab-all-spark",
        "version": "1.2.3",
        "values": {"foo": "bar"},
        "is_restricted": False,
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


@pytest.fixture
def create_app_request_superuser(rf, users):
    request = rf.post(reverse("create-app"))
    request.user = users["superuser"]
    return request


def test_create_app_form_clean_new_datasource(create_app_request_superuser):
    """
    The CreateAppForm class has a bespoke "clean" method. We should ensure it
    checks the expected things in the correct way.
    """
    f = forms.CreateAppForm(
        data={
            "repo_url": "https://github.com/ministryofjustice/my_repo",
            "connect_bucket": "new",
            "new_datasource_name": "test-bucketname",
            "namespace": "my-repo"
        },
        request=create_app_request_superuser,
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
            "deployment_envs": ["test"],
            "repo_url": "https://github.com/ministryofjustice/my_repo",
            "connect_bucket": "new",
            "namespace": "my-repo"
        },
        request=create_app_request_superuser,
    )
    f.clean_repo_url = mock.MagicMock()
    assert f.is_valid() is False
    assert "new_datasource_name" in f.errors
    assert "This field is required" in f.errors["new_datasource_name"][0]
    # If a datasource already exists, report the duplication.
    f = forms.CreateAppForm(
        data={
            "deployment_envs": ["test"],
            "repo_url": "https://github.com/ministryofjustice/my_repo",
            "connect_bucket": "new",
            "new_datasource_name": "test-bucketname",
        },
        request=create_app_request_superuser,
    )
    f.clean_repo_url = mock.MagicMock()
    mock_s3 = mock.MagicMock()
    with mock.patch("controlpanel.frontend.forms.S3Bucket.objects", mock_s3):
        assert f.is_valid() is False
        assert "Datasource named test-bucketname already exists" in f.errors["new_datasource_name"][0]


def test_create_app_form_clean_existing_datasource(create_app_request_superuser):
    """
    An existing datasource name is required if the datasource is marked as
    already existing.
    """
    f = forms.CreateAppForm(
        data={
            "repo_url": "https://github.com/moj-analytical-services/my_repo",
            "connect_bucket": "existing",
            "connections": ["email"],
        },
        request=create_app_request_superuser,
    )
    f.clean_repo_url = mock.MagicMock()
    # A valid form returns True.
    assert f.is_valid() is False
    assert "existing_datasource_id" in f.errors


def test_create_app_form_new_datasource_but_bucket_existed(create_app_request_superuser):
    bucket_name = "test-bucketname"
    aws.AWSBucket().create(bucket_name, is_data_warehouse=True)

    f = forms.CreateAppForm(
        data={
            "repo_url": "https://github.com/moj-analytical-services/my_repo",
            "connect_bucket": "new",
            "new_datasource_name": bucket_name,
            "connections": ["email"],
        },
        request=create_app_request_superuser,
    )
    f.clean_repo_url = mock.MagicMock()
    assert f.is_valid() is False
    assert "already exists" in ".".join(f.errors["new_datasource_name"])


def test_create_new_datasource_but_bucket_existed():
    bucket_name = "test-bucketname"
    aws.AWSBucket().create(bucket_name, is_data_warehouse=True)

    f = forms.CreateDatasourceForm(
        data={
            "name": bucket_name,
        }
    )
    assert f.is_valid() is False
    assert "already exists" in ".".join(f.errors["name"])


def test_create_new_datasource_folder_exists(root_folder_bucket):
    root_folder_bucket.put_object(Key='test-folder/')
    form = forms.CreateDatasourceFolderForm(
        data={"name": "test-folder"}
    )

    assert form.is_valid() is False
    assert "Folder 'test-folder' already exists" in form.errors["name"]


@pytest.mark.parametrize(
    "path, expected_error",
    [
        ("noslash", "Enter paths prefixed with a forward slash"),
        ("/trailingslash/", "Enter paths without a trailing forward slash"),
        ("/valid", None),
    ]
)
def test_grant_access_form_clean_paths(path, expected_error):
    data = {
        "paths": [path]
    }
    form = forms.GrantAccessForm()
    form.cleaned_data = data

    if expected_error:
        with pytest.raises(ValidationError, match=expected_error):
            form.clean_paths()
    else:
        assert form.clean_paths() == [path]


def test_create_app_form_clean_repo_url(create_app_request_superuser):
    """
    Ensure the various states of a GitHub repository result in a valid form or
    errors.
    """
    # The good case.
    f = forms.CreateAppForm(
        data={
            "repo_url": "https://github.com/ministryofjustice/my_repo",
            "connect_bucket": "new",
            "new_datasource_name": "test-bucketname",
            "namespace": "my-repo"
        },
        request=create_app_request_superuser,
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

    # App already exists.
    f = forms.CreateAppForm(
        data={
            "repo_url": "https://github.com/ministryofjustice/my_repo",
            "connect_bucket": "new",
            "new_datasource_name": "test-bucketname",
        },
        request=create_app_request_superuser
    )
    f.request = mock.MagicMock()
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
        assert f.errors["repo_url"][0] == "App already exists for this repository URL"

    # Repo in correct org but not found
    f = forms.CreateAppForm(
        data={
            "repo_url": "https://github.com/ministryofjustice/doesnt-exist",
            "connect_bucket": "new",
            "new_datasource_name": "test-bucketname",
        },
        request=create_app_request_superuser,
    )
    f.request = mock.MagicMock()
    mock_app = mock.MagicMock()
    mock_app.objects.filter().exists.return_value = False
    with mock.patch(
            "controlpanel.frontend.forms.GithubAPI.get_repository",
            side_effect=RepositoryNotFound
    ), mock.patch("controlpanel.frontend.forms.App", mock_app), mock.patch(
        "controlpanel.frontend.forms.S3Bucket.objects", mock_s3
    ):
        assert f.is_valid() is False
        error = f.errors["repo_url"][0]
        assert "Github repository not found - it may be private" in error


@pytest.mark.parametrize("user", ["superuser", "normal_user", "other_user"])
def test_create_app_form_get_datasource_queryset(users, rf, user):
    """
    Assert that for each user,
    """
    superuser_bucket = S3Bucket.objects.create(
        name="superuser_bucket",
        created_by=users["superuser"],
        is_data_warehouse=False,
    )
    user_bucket = S3Bucket.objects.create(
        name="user_bucket",
        created_by=users["normal_user"],
        is_data_warehouse=False,
    )
    warehouse_bucket = S3Bucket.objects.create(
        name="warehouse_bucket",
        created_by=users["superuser"],
        is_data_warehouse=True,
    )
    expected_buckets = {
        "superuser": [superuser_bucket, user_bucket],
        "normal_user": [user_bucket],
        "other_user": []
    }

    request = rf.post(reverse("create-app"))
    request.user = users[user]
    form = forms.CreateAppForm(request=request)

    queryset = form.get_datasource_queryset()

    assert list(queryset) == expected_buckets[user]
    assert warehouse_bucket not in expected_buckets[user]


def test_update_app_with_custom_connection():
    # Good case.
    f = forms.UpdateAppAuth0ConnectionsForm(
        data={
            "env_name": "test",
            "connections": ["email", "auth0_nomis"],
            "auth0_nomis_auth0_client_id": "nomis-client-id",
            "auth0_nomis_auth0_client_secret": "nomis-client-secret",
            "auth0_nomis_auth0_conn_name": "nomis-conn-name",
        },
        all_connections_names=["github", "email", "auth0_nomis"],
        custom_connections=["auth0_nomis"],
        auth0_connections=["github"],
    )
    f.request = mock.MagicMock()
    mock_app = mock.MagicMock()
    mock_app.objects.filter().exists.return_value = False
    with mock.patch("controlpanel.frontend.forms.App", mock_app):
        assert f.is_valid() is True

    # Bad case: missing client credential for nomis login + not valid connection name
    f = forms.UpdateAppAuth0ConnectionsForm(
        data={
            "env_name": "test",
            "connections": ["email", "auth0_nomis"],
            "auth0_nomis_auth0_client_id": "nomis-client-id",
            "auth0_nomis_auth0_client_secret": "",
            "auth0_nomis_auth0_conn_name": "nomis_conn_name",
        },
        all_connections_names=["github", "email", "auth0_nomis"],
        custom_connections=["auth0_nomis"],
        auth0_connections=["github"],
    )
    f.request = mock.MagicMock()
    mock_app = mock.MagicMock()
    mock_app.objects.filter().exists.return_value = False
    with mock.patch("controlpanel.frontend.forms.App", mock_app):
        assert f.is_valid() is False
        assert "auth0_nomis_auth0_client_secret" in f.errors
        assert "auth0_nomis_auth0_conn_name" in f.errors


@pytest.mark.django_db
def test_ip_allowlist_form_invalid_ip():
    """
    Make sure invalid IP allowlist configurations throw errors as expected
    (See also validation tests in ../test_validators.py)
    """
    data = {
        "name": "An IP allowlist",
        "allowed_ip_ranges": "123, 456",
    }
    f = forms.IPAllowlistForm(data)
    assert f.errors["allowed_ip_ranges"] == [
        "123 should be an IPv4 or IPv6 address (in a comma-separated list if several IP addresses are provided)."  # noqa: E501
    ]


@pytest.mark.django_db
def test_ip_allowlist_form_missing_ip():
    data = {
        "name": "An IP allowlist",
        "allowed_ip_ranges": "",
    }
    f = forms.IPAllowlistForm(data)
    assert f.errors["allowed_ip_ranges"] == ["This field is required."]


@pytest.mark.django_db
def test_ip_allowlist_form_missing_name():
    data = {
        "name": "",
        "allowed_ip_ranges": "192.168.0.0/28",
    }
    f = forms.IPAllowlistForm(data)
    assert f.errors["name"] == ["This field is required."]


@pytest.mark.parametrize("env", ["dev", "prod"])
@mock.patch(
    "controlpanel.frontend.forms.CreateAppForm.get_datasource_queryset",
    new=mock.MagicMock,
)
def test_clean_namespace(env):
    form = forms.CreateAppForm()
    form.cleaned_data = {"namespace": f"my-namespace-{env}"}

    assert form.clean_namespace() == "my-namespace"
