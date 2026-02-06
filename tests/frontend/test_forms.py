# Standard library
from unittest import mock

# Third-party
import pytest
from django.core.exceptions import ValidationError
from django.http import QueryDict
from django.urls import reverse
from model_bakery import baker

# First-party/Local
from controlpanel.api import aws
from controlpanel.api.github import RepositoryNotFound
from controlpanel.api.models import DashboardViewer, DashboardViewerAccess, S3Bucket
from controlpanel.api.models.user import QUICKSIGHT_EMBED_AUTHOR_PERMISSION
from controlpanel.frontend import forms
from controlpanel.frontend.forms import (
    AddDashboardAdminForm,
    AddDashboardViewersForm,
    MultiEmailField,
    MultiEmailWidget,
    MultiUserField,
    MultiUserWidget,
)


class TestMultiEmailWidgetValueFromDatadict:
    """Tests for MultiEmailWidget.value_from_datadict method."""

    def test_empty_data_returns_empty_list(self):
        """When no matching keys exist, returns empty list."""
        widget = MultiEmailWidget()
        data = {}
        result = widget.value_from_datadict(data, {}, "emails")
        assert result == []

    def test_single_email(self):
        """Extracts a single email from emails[0]."""
        widget = MultiEmailWidget()
        data = {"emails[0]": "test@example.com"}
        result = widget.value_from_datadict(data, {}, "emails")
        assert result == ["test@example.com"]

    def test_multiple_emails(self):
        """Extracts multiple emails from sequential indices."""
        widget = MultiEmailWidget()
        data = {
            "emails[0]": "first@example.com",
            "emails[1]": "second@example.com",
            "emails[2]": "third@example.com",
        }
        result = widget.value_from_datadict(data, {}, "emails")
        assert result == ["first@example.com", "second@example.com", "third@example.com"]

    def test_strips_whitespace(self):
        """Strips leading and trailing whitespace from values."""
        widget = MultiEmailWidget()
        data = {
            "emails[0]": "  test@example.com  ",
            "emails[1]": "\tother@example.com\n",
        }
        result = widget.value_from_datadict(data, {}, "emails")
        assert result == ["test@example.com", "other@example.com"]

    def test_skips_empty_values(self):
        """Empty values (after stripping) are not included."""
        widget = MultiEmailWidget()
        data = {
            "emails[0]": "first@example.com",
            "emails[1]": "",
            "emails[2]": "   ",
            "emails[3]": "third@example.com",
        }
        result = widget.value_from_datadict(data, {}, "emails")
        assert result == ["first@example.com", "third@example.com"]

    def test_stops_at_first_missing_index(self):
        """Stops extracting when an index is missing (gap in sequence)."""
        widget = MultiEmailWidget()
        data = {
            "emails[0]": "first@example.com",
            "emails[1]": "second@example.com",
            # emails[2] is missing
            "emails[3]": "should-not-be-included@example.com",
        }
        result = widget.value_from_datadict(data, {}, "emails")
        assert result == ["first@example.com", "second@example.com"]

    def test_different_field_name(self):
        """Works with different field names."""
        widget = MultiEmailWidget()
        data = {
            "recipients[0]": "one@example.com",
            "recipients[1]": "two@example.com",
        }
        result = widget.value_from_datadict(data, {}, "recipients")
        assert result == ["one@example.com", "two@example.com"]

    def test_ignores_unrelated_keys(self):
        """Only extracts keys matching the specified name pattern."""
        widget = MultiEmailWidget()
        data = {
            "emails[0]": "correct@example.com",
            "other_field": "ignored",
            "emails": "also-ignored",
        }
        result = widget.value_from_datadict(data, {}, "emails")
        assert result == ["correct@example.com"]

    def test_with_querydict(self):
        """Works with Django QueryDict (as used in request.POST)."""
        widget = MultiEmailWidget()
        data = QueryDict("emails[0]=first@example.com&emails[1]=second@example.com")
        result = widget.value_from_datadict(data, {}, "emails")
        assert result == ["first@example.com", "second@example.com"]


class TestMultiEmailFieldClean:
    """Tests for MultiEmailField.clean method."""

    def test_empty_value_not_required_returns_empty_list(self):
        """When not required and no value, returns empty list."""
        field = MultiEmailField(required=False)
        assert field.clean([]) == []
        assert field.clean(None) == []

    def test_empty_value_required_raises_error(self):
        """When required and no value, raises ValidationError."""
        field = MultiEmailField(required=True)
        with pytest.raises(ValidationError):
            field.clean([])

    def test_converts_emails_to_lowercase(self):
        """Emails are converted to lowercase."""
        field = MultiEmailField()
        result = field.clean(["TEST@EXAMPLE.COM", "Another@Example.Org"])
        assert result == ["test@example.com", "another@example.org"]

    def test_invalid_email_raises_error(self):
        """Invalid email addresses raise ValidationError."""
        field = MultiEmailField()
        with pytest.raises(ValidationError) as exc_info:
            field.clean(["not-an-email"])
        assert "Enter a valid email address" in str(exc_info.value)

    def test_multiple_invalid_emails_shows_all_errors(self):
        """All invalid emails are reported, not just the first."""
        field = MultiEmailField()
        with pytest.raises(ValidationError) as exc_info:
            field.clean(["bad1", "valid@example.com", "bad2"])
        errors = exc_info.value.messages
        assert len(errors) == 2
        assert "Enter a valid email address" in errors
        assert "Enter a valid email address" in errors

    def test_index_errors_tracks_which_emails_are_invalid(self):
        """index_errors dict tracks which specific indices had errors."""
        field = MultiEmailField()
        with pytest.raises(ValidationError):
            field.clean(["valid@example.com", "invalid", "also@valid.com", "bad"])

        # Only indices 1 and 3 should have errors
        assert field.index_errors.get(0) is None
        assert field.index_errors.get(1) == "Enter a valid email address"
        assert field.index_errors.get(2) is None
        assert field.index_errors.get(3) == "Enter a valid email address"
        assert field.index_errors.get(99) is None  # Non-existent index


@pytest.fixture
def release_data():
    return {
        "name": "Test Release",
        "chart_name": "jupyter-lab",
        "version": "1.2.3",
        "values": {"foo": "bar"},
        "is_restricted": False,
        "image_tag": "1.0.0",
        "description": "Test release description",
    }


@pytest.mark.parametrize(
    "chart_name, expected",
    [
        ("jupyter-lab", True),
        ("rstudio", True),
        ("jupyter-lab-all-spark", True),
        ("vscode", True),
        ("jupyter-lab-datascience-notebook", True),
        ("invalid-chartname", False),
    ],
)
def test_tool_release_form_check_chart_name(db, release_data, chart_name, expected):
    """
    Ensure valid chart names work, while invalid ones cause a helpful
    exception.
    """
    release_data["chart_name"] = chart_name
    f = forms.ToolReleaseForm(release_data)
    assert f.is_valid() is expected


@pytest.mark.parametrize(
    "tool_domain, expected",
    [("jupyter-lab", True), ("rstudio", True), ("vscode", True), ("invalid-tool-domain", False)],
)
def test_tool_release_form_check_tool_domain(db, release_data, tool_domain, expected):
    """
    Ensure ONLY valid chart names work, while invalid ones cause a helpful
    exception.
    """
    release_data["tool_domain"] = tool_domain

    f = forms.ToolReleaseForm(release_data)
    assert f.is_valid() is expected


def test_tool_release_form_clean_target_users():
    """
    Given a string list of comma separated usernames, the expected query to
    return the associated User objects is created.
    """
    f = forms.ToolReleaseForm()
    f.cleaned_data = {
        "target_users_list": "aldo, nicholas, cal, MICHAEL",
    }
    with mock.patch("controlpanel.frontend.forms.User") as mock_user:
        mock_user.objects.filter.return_value.values_list.return_value = [
            "aldo",
            "nicholas",
            "cal",
            "michael",
        ]
        result = f.clean_target_users_list()

        mock_user.objects.filter.assert_called_once_with(
            username__in=set(["aldo", "nicholas", "cal", "michael"])
        )
        mock_user.objects.filter.return_value.values_list.assert_called_once_with(
            "username", flat=True
        )
        assert result == mock_user.objects.filter.return_value


def test_tool_release_form_clean_target_users_not_found():
    """
    Given a string list of comma separated usernames, the expected query to
    return the associated User objects is created.
    """
    f = forms.ToolReleaseForm()
    f.cleaned_data = {
        "target_users_list": "missing_user, ANOTHER_MISSING_USER",
    }
    with mock.patch("controlpanel.frontend.forms.User") as mock_user:
        mock_user.objects.filter.return_value.values_list.return_value = []

        with pytest.raises(ValidationError) as excinfo:
            f.clean_target_users_list()
            assert excinfo.value.message == "Users not found: another_missing_user, missing_user"

        mock_user.objects.filter.assert_called_once_with(
            username__in=set(["missing_user", "another_missing_user"]),
        )
        mock_user.objects.filter.return_value.values_list.assert_called_once_with(
            "username", flat=True
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
            "namespace": "my-repo",
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
            "namespace": "my-repo",
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
        assert (
            "Datasource named test-bucketname already exists" in f.errors["new_datasource_name"][0]
        )


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
    root_folder_bucket.put_object(Key="test-folder/")
    form = forms.CreateDatasourceFolderForm(data={"name": "test-folder"})

    assert form.is_valid() is False
    assert "Folder 'test-folder' already exists" in form.errors["name"]


@pytest.mark.parametrize(
    "path, expected_error",
    [
        ("noslash", "Enter paths prefixed with a forward slash"),
        ("/trailingslash/", "Enter paths without a trailing forward slash"),
        ("/valid", None),
    ],
)
def test_grant_access_form_clean_paths(path, expected_error):
    data = {"paths": [path]}
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
            "namespace": "my-repo",
        },
        request=create_app_request_superuser,
    )
    f.request = mock.MagicMock()
    mock_get_repo = mock.MagicMock(return_value=True)
    mock_app = mock.MagicMock()
    mock_app.objects.filter().exists.return_value = False
    mock_s3 = mock.MagicMock()
    mock_s3.get.side_effect = S3Bucket.DoesNotExist("Boom")
    with (
        mock.patch("controlpanel.frontend.forms.GithubAPI.get_repository", mock_get_repo),
        mock.patch("controlpanel.frontend.forms.App", mock_app),
        mock.patch("controlpanel.frontend.forms.S3Bucket.objects", mock_s3),
    ):
        assert f.is_valid() is True

    # App already exists.
    f = forms.CreateAppForm(
        data={
            "repo_url": "https://github.com/ministryofjustice/my_repo",
            "connect_bucket": "new",
            "new_datasource_name": "test-bucketname",
        },
        request=create_app_request_superuser,
    )
    f.request = mock.MagicMock()
    mock_app = mock.MagicMock()
    mock_app.objects.filter().exists.return_value = True
    mock_s3 = mock.MagicMock()
    mock_s3.get.side_effect = S3Bucket.DoesNotExist("Boom")
    with (
        mock.patch("controlpanel.frontend.forms.GithubAPI.get_repository", mock_get_repo),
        mock.patch("controlpanel.frontend.forms.App", mock_app),
        mock.patch("controlpanel.frontend.forms.S3Bucket.objects", mock_s3),
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
    with (
        mock.patch(
            "controlpanel.frontend.forms.GithubAPI.get_repository", side_effect=RepositoryNotFound
        ),
        mock.patch("controlpanel.frontend.forms.App", mock_app),
        mock.patch("controlpanel.frontend.forms.S3Bucket.objects", mock_s3),
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
        "other_user": [],
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


class TestMultiUserWidgetValueFromDatadict:
    """Tests for MultiUserWidget.value_from_datadict method."""

    def test_empty_data_returns_empty_list(self):
        """When no matching keys exist, returns empty list."""
        widget = MultiUserWidget()
        data = {}
        result = widget.value_from_datadict(data, {}, "users")
        assert result == []

    def test_single_user(self):
        """Extracts a single user ID from users[0]."""
        widget = MultiUserWidget()
        data = {"users[0]": "github|123"}
        result = widget.value_from_datadict(data, {}, "users")
        assert result == ["github|123"]

    def test_multiple_users(self):
        """Extracts multiple user IDs from sequential indices."""
        widget = MultiUserWidget()
        data = {
            "users[0]": "github|1",
            "users[1]": "github|2",
            "users[2]": "github|3",
        }
        result = widget.value_from_datadict(data, {}, "users")
        assert result == ["github|1", "github|2", "github|3"]

    def test_strips_whitespace(self):
        """Strips leading and trailing whitespace from values."""
        widget = MultiUserWidget()
        data = {
            "users[0]": "  github|1  ",
            "users[1]": "\tgithub|2\n",
        }
        result = widget.value_from_datadict(data, {}, "users")
        assert result == ["github|1", "github|2"]

    def test_skips_empty_values(self):
        """Empty values (after stripping) are not included."""
        widget = MultiUserWidget()
        data = {
            "users[0]": "github|1",
            "users[1]": "",
            "users[2]": "   ",
            "users[3]": "github|2",
        }
        result = widget.value_from_datadict(data, {}, "users")
        assert result == ["github|1", "github|2"]

    def test_stops_at_first_missing_index(self):
        """Stops extracting when an index is missing (gap in sequence)."""
        widget = MultiUserWidget()
        data = {
            "users[0]": "github|1",
            "users[1]": "github|2",
            # users[2] is missing
            "users[3]": "github|3",
        }
        result = widget.value_from_datadict(data, {}, "users")
        assert result == ["github|1", "github|2"]


class TestMultiUserFieldClean:
    """Tests for MultiUserField.clean method."""

    def test_empty_value_not_required_returns_empty_list(self, db):
        """When not required and no value, returns empty list."""
        field = MultiUserField(required=False)
        assert field.clean([]) == []
        assert field.clean(None) == []

    def test_empty_value_required_raises_error(self, db):
        """When required and no value, raises ValidationError."""
        field = MultiUserField(required=True)
        with pytest.raises(ValidationError) as exc_info:
            field.clean([])
        assert "Select a user" in str(exc_info.value)

    def test_valid_user_returns_user_objects(self, db):
        """Valid auth0_ids return User objects."""
        # Third-party
        from model_bakery import baker

        user = baker.make("api.User", auth0_id="github|test123")
        field = MultiUserField()
        result = field.clean(["github|test123"])
        assert len(result) == 1
        assert result[0] == user

    def test_invalid_user_raises_error(self, db):
        """Invalid auth0_id raises ValidationError with index-specific error."""
        field = MultiUserField()
        with pytest.raises(ValidationError) as exc_info:
            field.clean(["nonexistent|user"])
        assert "User not found" in str(exc_info.value)
        assert field.index_errors == {0: "User not found"}

    def test_multiple_users_some_invalid(self, db):
        """If any user is invalid, raises ValidationError with index-specific error."""
        # Third-party
        from model_bakery import baker

        baker.make("api.User", auth0_id="github|valid")
        field = MultiUserField()
        with pytest.raises(ValidationError) as exc_info:
            field.clean(["github|valid", "github|invalid"])
        assert "User not found" in str(exc_info.value)
        # Only the invalid user at index 1 should have an error
        assert field.index_errors == {1: "User not found"}


class TestAddDashboardAdminForm:
    """Tests for AddDashboardAdminForm."""

    @pytest.fixture
    def dashboard(self, db):
        # Third-party
        from model_bakery import baker

        return baker.make("api.Dashboard")

    @pytest.fixture
    def quicksight_user(self, db):
        # Third-party
        from django.contrib.auth.models import Permission
        from model_bakery import baker

        user = baker.make("api.User", auth0_id="github|qs_user")
        user.user_permissions.add(
            Permission.objects.get(codename=QUICKSIGHT_EMBED_AUTHOR_PERMISSION)
        )
        return user

    @pytest.fixture
    def non_quicksight_user(self, db):
        # Third-party
        from model_bakery import baker

        return baker.make("api.User", auth0_id="github|normal_user")

    @pytest.fixture
    def admin_user(self, db):
        # Third-party
        from model_bakery import baker

        return baker.make("api.User", auth0_id="github|admin")

    def test_get_user_options_returns_quicksight_users(
        self, dashboard, quicksight_user, non_quicksight_user, admin_user
    ):
        """get_user_options returns only quicksight users not already admins."""
        form = AddDashboardAdminForm(dashboard=dashboard, added_by=admin_user)
        options = list(form.get_user_options())

        assert quicksight_user in options
        assert non_quicksight_user not in options

    def test_get_user_options_excludes_existing_admins(
        self, dashboard, quicksight_user, admin_user
    ):
        """get_user_options excludes users who are already admins."""
        # Third-party
        from django.contrib.auth.models import Permission

        # Make admin_user a quicksight user and add as admin
        admin_user.user_permissions.add(
            Permission.objects.get(codename=QUICKSIGHT_EMBED_AUTHOR_PERMISSION)
        )
        dashboard.admins.add(admin_user)

        form = AddDashboardAdminForm(dashboard=dashboard, added_by=admin_user)
        options = list(form.get_user_options())

        assert quicksight_user in options
        assert admin_user not in options

    def test_clean_users_rejects_non_quicksight_users(
        self, dashboard, quicksight_user, non_quicksight_user, admin_user
    ):
        """clean_users rejects users who are not quicksight users."""
        form = AddDashboardAdminForm(
            data={"users[0]": non_quicksight_user.auth0_id},
            dashboard=dashboard,
            added_by=admin_user,
        )
        assert not form.is_valid()
        assert "One or more selected users cannot be added as admins" in str(form.errors)

    def test_clean_users_rejects_existing_admins(self, dashboard, quicksight_user, admin_user):
        """clean_users rejects users who are already admins.

        Note: Existing admins are excluded from get_user_options(), so they
        fail the 'cannot be added as admins' validation check.
        """
        # First-party/Local
        from controlpanel.api.models import DashboardAdminAccess

        DashboardAdminAccess.objects.create(
            dashboard=dashboard, user=quicksight_user, added_by=admin_user
        )

        form = AddDashboardAdminForm(
            data={"users[0]": quicksight_user.auth0_id},
            dashboard=dashboard,
            added_by=admin_user,
        )
        assert not form.is_valid()
        assert "One or more selected users cannot be added as admins" in str(form.errors)

    def test_save_creates_dashboard_admin_access(self, dashboard, quicksight_user, admin_user):
        """save() creates DashboardAdminAccess records."""
        # First-party/Local
        from controlpanel.api.models import DashboardAdminAccess

        form = AddDashboardAdminForm(
            data={"users[0]": quicksight_user.auth0_id},
            dashboard=dashboard,
            added_by=admin_user,
        )
        assert form.is_valid(), form.errors
        added_users = form.save()

        assert len(added_users) == 1
        assert added_users[0] == quicksight_user
        assert DashboardAdminAccess.objects.filter(
            dashboard=dashboard, user=quicksight_user, added_by=admin_user
        ).exists()


class TestAddDashboardViewersForm:
    """Tests for AddDashboardViewersForm."""

    @pytest.fixture
    def ExtendedAuth0(self):
        with mock.patch("controlpanel.api.auth0.ExtendedAuth0") as ExtendedAuth0:
            ExtendedAuth0.return_value.add_dashboard_member_by_email.return_value = None
            yield ExtendedAuth0.return_value

    @pytest.fixture
    def dashboard(self, db, ExtendedAuth0):
        return baker.make("api.Dashboard")

    @pytest.fixture
    def shared_by_user(self, db):
        return baker.make(
            "api.User", auth0_id="github|sharer", justice_email="sharer@justice.gov.uk"
        )

    @pytest.fixture
    def existing_viewer(self, db, dashboard, ExtendedAuth0):
        viewer = baker.make(DashboardViewer, email="existing@example.com")
        DashboardViewerAccess.objects.create(dashboard=dashboard, viewer=viewer, shared_by=None)
        return viewer

    def test_valid_single_email(self, dashboard, shared_by_user):
        """Form accepts a valid single email address."""
        form = AddDashboardViewersForm(
            data={"emails[0]": "test@example.com"},
            dashboard=dashboard,
            shared_by=shared_by_user,
        )
        assert form.is_valid(), form.errors
        assert form.cleaned_data["emails"] == ["test@example.com"]

    def test_valid_multiple_emails(self, dashboard, shared_by_user):
        """Form accepts multiple valid email addresses."""
        form = AddDashboardViewersForm(
            data={"emails[0]": "test1@example.com", "emails[1]": "test2@example.com"},
            dashboard=dashboard,
            shared_by=shared_by_user,
        )
        assert form.is_valid(), form.errors
        assert set(form.cleaned_data["emails"]) == {"test1@example.com", "test2@example.com"}

    def test_emails_lowercased(self, dashboard, shared_by_user):
        """Form lowercases email addresses."""
        form = AddDashboardViewersForm(
            data={"emails[0]": "TEST@EXAMPLE.COM"},
            dashboard=dashboard,
            shared_by=shared_by_user,
        )
        assert form.is_valid(), form.errors
        assert form.cleaned_data["emails"] == ["test@example.com"]

    def test_invalid_email_rejected(self, dashboard, shared_by_user):
        """Form rejects invalid email addresses."""
        form = AddDashboardViewersForm(
            data={"emails[0]": "notanemail"},
            dashboard=dashboard,
            shared_by=shared_by_user,
        )
        assert not form.is_valid()
        assert "emails" in form.errors

    def test_empty_form_rejected(self, dashboard, shared_by_user):
        """Form rejects empty submission."""
        form = AddDashboardViewersForm(
            data={},
            dashboard=dashboard,
            shared_by=shared_by_user,
        )
        assert not form.is_valid()
        assert "emails" in form.errors

    def test_existing_viewers_filtered_out(self, dashboard, shared_by_user, existing_viewer):
        """Form filters out emails that are already viewers."""
        form = AddDashboardViewersForm(
            data={"emails[0]": "existing@example.com", "emails[1]": "new@example.com"},
            dashboard=dashboard,
            shared_by=shared_by_user,
        )
        assert form.is_valid(), form.errors
        assert form.cleaned_data["emails"] == ["new@example.com"]

    def test_all_existing_viewers_error(self, dashboard, shared_by_user, existing_viewer):
        """Form errors when all submitted emails are existing viewers."""
        form = AddDashboardViewersForm(
            data={"emails[0]": "existing@example.com"},
            dashboard=dashboard,
            shared_by=shared_by_user,
        )
        assert not form.is_valid()
        assert "All email addresses entered already have access" in str(form.errors)

    def test_save_creates_viewer_access(
        self, dashboard, shared_by_user, ExtendedAuth0, govuk_notify_send_email
    ):
        """save() creates DashboardViewerAccess records and notifies viewers."""
        form = AddDashboardViewersForm(
            data={"emails[0]": "newviewer@example.com"},
            dashboard=dashboard,
            shared_by=shared_by_user,
        )
        assert form.is_valid(), form.errors
        emails, not_notified = form.save()

        assert emails == ["newviewer@example.com"]
        assert not_notified == []
        assert DashboardViewerAccess.objects.filter(
            dashboard=dashboard,
            viewer__email="newviewer@example.com",
            shared_by=shared_by_user,
        ).exists()
        govuk_notify_send_email.assert_called_once()
