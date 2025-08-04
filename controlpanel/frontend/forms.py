# Standard library
import re

# Third-party
from django import forms
from django.conf import settings
from django.contrib.auth.models import Permission
from django.contrib.postgres.forms import SimpleArrayField
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator, validate_email
from django.db.models import Q

# First-party/Local
from controlpanel.api import validators
from controlpanel.api.aws import AWSIdentityStore, AWSQuicksight
from controlpanel.api.cluster import AWSRoleCategory
from controlpanel.api.cluster import S3Folder as ClusterS3Folder
from controlpanel.api.github import GithubAPI, RepositoryNotFound, extract_repo_info_from_url
from controlpanel.api.models import (
    QUICKSIGHT_EMBED_AUTHOR_PERMISSION,
    QUICKSIGHT_EMBED_READER_PERMISSION,
    App,
    Dashboard,
    DashboardDomain,
    Feedback,
    S3Bucket,
    Tool,
    User,
)
from controlpanel.api.models.access_to_s3bucket import S3BUCKET_PATH_REGEX
from controlpanel.api.models.iam_managed_policy import POLICY_NAME_REGEX
from controlpanel.api.models.ip_allowlist import IPAllowlist
from controlpanel.api.models.tool import ToolDeployment
from controlpanel.utils import build_tool_url

CUSTOMERS_DELIMITERS = re.compile(r"[,; ]+")


class DatasourceChoiceField(forms.ModelChoiceField):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.widget.attrs["class"] = "govuk-select govuk-!-width-one-half"

    def label_from_instance(self, instance):
        return instance.name


class DynamicMultiChoiceField(forms.MultipleChoiceField):

    def validate(self, value):
        """Only validate whether required feature, nothing else"""
        if self.required and not value:
            raise ValidationError(self.error_messages["required"], code="required")


class AppAuth0Form(forms.Form):
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        self.auth0_connections = kwargs.pop("auth0_connections", ["email"])
        self.all_connections_names = kwargs.pop("all_connections_names", ["email"])
        self.custom_connections = kwargs.pop("custom_connections", [])
        super(AppAuth0Form, self).__init__(*args, **kwargs)

        self._create_inputs_for_custom_connections()

    def _create_inputs_for_custom_connections(self):
        self.fields["connections"] = forms.MultipleChoiceField(
            required=False,
            initial=self.auth0_connections,
            choices=list(zip(self.all_connections_names, self.all_connections_names)),
        )
        for connection in self.custom_connections:
            self.fields["{}_auth0_client_id".format(connection)] = forms.CharField(
                max_length=128,
                required=False,
                validators=[validators.validate_auth0_client_id],
            )
            self.fields["{}_auth0_client_secret".format(connection)] = forms.CharField(
                widget=forms.PasswordInput, required=False
            )
            self.fields["{}_auth0_conn_name".format(connection)] = forms.CharField(
                max_length=128,
                required=False,
                validators=[validators.validate_auth0_conn_name],
            )

    def _chosen_custom_connections(self, connections):
        return list(set(self.custom_connections) & set(connections or []))

    def _check_inputs_for_custom_connection(self, cleaned_data):
        auth0_connections = cleaned_data.get("connections") or []
        auth0_conn_data = {}
        chosen_custom_connections = self._chosen_custom_connections(auth0_connections)
        for connection in auth0_connections:
            auth0_conn_data[connection] = {}
            if connection not in chosen_custom_connections:
                continue

            if cleaned_data.get("{}_auth0_client_id".format(connection), "") == "":
                self.add_error("{}_auth0_client_id".format(connection), "This field is required.")

            if cleaned_data.get("{}_auth0_client_secret".format(connection), "") == "":
                self.add_error(
                    "{}_auth0_client_secret".format(connection),
                    "This field is required.",
                )

            conn_name = cleaned_data.get("{}_auth0_conn_name".format(connection), "")
            if conn_name == "":
                self.add_error("{}_auth0_conn_name".format(connection), "This field is required.")
            elif (conn_name, conn_name) in self.fields["connections"].choices:
                self.add_error(
                    "{}_auth0_conn_name".format(connection),
                    "This name has been existed in the connections.",
                )

            auth0_conn_data[connection] = {
                "client_id": cleaned_data.get("{}_auth0_client_id".format(connection)),
                "client_secret": cleaned_data.get("{}_auth0_client_secret".format(connection)),
                "name": cleaned_data.get("{}_auth0_conn_name".format(connection)),
            }
        return auth0_conn_data


class CreateAppForm(forms.Form):

    repo_url = forms.CharField(
        max_length=512,
        validators=[
            validators.validate_github_repository_url,
        ],
    )
    connect_bucket = forms.ChoiceField(
        required=True,
        initial="new",
        choices=[
            ("new", "new"),
            ("existing", "existing"),
            ("later", "later"),
        ],
    )
    new_datasource_name = forms.CharField(
        max_length=63,
        validators=[
            validators.validate_env_prefix,
            validators.validate_s3_bucket_labels,
            validators.validate_s3_bucket_length,
            validators.ValidatorS3Bucket(AWSRoleCategory.app),
        ],
        required=False,
    )
    existing_datasource_id = DatasourceChoiceField(
        queryset=S3Bucket.objects.none(),
        empty_label="Select",
        required=False,
    )
    namespace = forms.CharField(required=True, max_length=63)
    allow_cloud_platform_assume_role = forms.BooleanField(initial=False, required=False)
    cloud_platform_role_arn = forms.CharField(
        required=False, max_length=130, validators=[validators.validate_aws_role_arn]
    )

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)
        self.fields["existing_datasource_id"].queryset = self.get_datasource_queryset()

    def get_datasource_queryset(self):
        queryset = S3Bucket.objects.filter(is_data_warehouse=False, is_deleted=False)
        if self.request.user.is_superuser:
            return queryset

        user_admin_buckets = self.request.user.users3buckets.filter(is_admin=True)
        queryset = queryset.filter(users3buckets__in=user_admin_buckets)
        return queryset

    def clean(self):
        cleaned_data = super().clean()
        connect_data_source = cleaned_data["connect_bucket"]
        new_datasource = cleaned_data.get("new_datasource_name")
        existing_datasource = cleaned_data.get("existing_datasource_id")

        if connect_data_source == "new":
            if new_datasource:
                try:
                    S3Bucket.objects.get(name=new_datasource)
                    self.add_error(
                        "new_datasource_name",
                        f"Datasource named {new_datasource} already exists",
                    )
                except S3Bucket.DoesNotExist:
                    pass

            else:
                self.add_error("new_datasource_name", "This field is required.")

        if connect_data_source == "existing" and not existing_datasource:
            self.add_error("existing_datasource_id", "This field is required.")

        assume_role = cleaned_data.get("allow_cloud_platform_assume_role")
        role_arn = cleaned_data.get("cloud_platform_role_arn")

        if assume_role and not role_arn:
            self.add_error("cloud_platform_role_arn", "Role ARN is required")

        if not assume_role and role_arn:
            cleaned_data.pop("cloud_platform_role_arn")

        return cleaned_data

    def clean_repo_url(self):
        repo_url = self.cleaned_data["repo_url"]
        org_name, repo_name = extract_repo_info_from_url(repo_url)
        try:
            GithubAPI(self.request.user.github_api_token, github_org=org_name).get_repository(
                repo_name
            )
        except RepositoryNotFound:
            raise ValidationError(
                "Github repository not found - it may be private",
            )

        if App.objects.filter(repo_url=repo_url).exists():
            raise ValidationError("App already exists for this repository URL")

        return repo_url

    def clean_namespace(self):
        """
        Removes the env suffix if the user included it
        """
        namespace = self.cleaned_data["namespace"]
        for suffix in ["-dev", "-prod"]:
            if suffix in namespace:
                namespace = namespace.removesuffix(suffix)
                break

        return namespace


class CloudPlatformArnForm(forms.Form):
    allow_cloud_platform_assume_role = forms.BooleanField(initial=False, required=False)
    cloud_platform_role_arn = forms.CharField(
        required=False, max_length=130, validators=[validators.validate_aws_role_arn]
    )

    def clean(self):
        cleaned_data = super().clean()
        assume_role = cleaned_data.get("allow_cloud_platform_assume_role")
        role_arn = cleaned_data.get("cloud_platform_role_arn")

        if assume_role and not role_arn:
            self.add_error("cloud_platform_role_arn", "Role ARN is required")

        if not assume_role and role_arn:
            cleaned_data.pop("cloud_platform_role_arn")

        return cleaned_data


class UpdateAppAuth0ConnectionsForm(AppAuth0Form):
    env_name = forms.CharField(widget=forms.HiddenInput)

    def __init__(self, *args, **kwargs):
        self.env_name = kwargs.pop("env_name", "")
        super(UpdateAppAuth0ConnectionsForm, self).__init__(*args, **kwargs)

        self._create_inputs_for_custom_connections()
        self.fields["env_name"].initial = self.env_name

    def clean(self):
        cleaned_data = super(UpdateAppAuth0ConnectionsForm, self).clean()
        cleaned_data["auth0_connections"] = self._check_inputs_for_custom_connection(cleaned_data)
        return cleaned_data


class CreateDatasourceForm(forms.Form):
    name = forms.CharField(
        max_length=63,
        validators=[
            validators.validate_env_prefix,
            validators.validate_s3_bucket_labels,
            validators.validate_s3_bucket_length,
            validators.ValidatorS3Bucket(AWSRoleCategory.user),
        ],
    )


class CreateDatasourceFolderForm(forms.Form):

    name = forms.CharField(
        max_length=100,
        min_length=3,
        validators=[
            validators.validate_s3_bucket_labels,
            validators.validate_env_prefix,
        ],
    )

    def clean_name(self):
        """
        Ensure that the name of the folder to be created does not already exist in the
        S3 bucket. Then return the name with the bucket name prefixed, so that the full
        path to the folder is stored against the object.
        """
        folder_name = self.cleaned_data["name"]
        exists, folder_path = ClusterS3Folder(None).exists(
            folder_name=folder_name, bucket_owner=AWSRoleCategory.user
        )
        if exists:
            raise ValidationError(f"Folder '{folder_name}' already exists")

        return folder_path


class GrantAccessForm(forms.Form):
    access_level = forms.ChoiceField(
        choices=[
            ("readonly", "Read only"),
            ("readwrite", "Read/write"),
            ("admin", "Admin"),
        ],
        required=True,
    )
    paths = SimpleArrayField(
        forms.CharField(
            max_length=255,
            validators=[
                RegexValidator(S3BUCKET_PATH_REGEX),
            ],
            required=True,
        ),
        label="Paths (optional)",
        help_text=(
            "Add specific paths for this user or group to access or leave blank "
            "for full access. Paths must be separated by a newline, with a "
            "leading forward slash and no trailing slash. For example: /my-path"
        ),
        required=False,
        delimiter="\n",
    )
    is_admin = forms.BooleanField(initial=False, required=False)
    entity_id = forms.CharField(max_length=128)
    entity_type = forms.ChoiceField(
        choices=[
            ("group", "group"),
            ("user", "user"),
        ],
        widget=forms.HiddenInput(),
        required=True,
    )

    def clean(self):
        cleaned_data = super().clean()
        access_level = cleaned_data.get("access_level")
        if access_level == "admin":
            cleaned_data["access_level"] = "readwrite"
            cleaned_data["is_admin"] = True

        if cleaned_data["entity_type"] == "user":
            cleaned_data["user_id"] = cleaned_data.get("entity_id")
        elif cleaned_data["entity_type"] == "group":
            cleaned_data["policy_id"] = cleaned_data.get("entity_id")

        return cleaned_data

    def clean_paths(self):
        """
        Validation to ensure paths are entered with a leading forward slash, and without
        trailing slash. This is to ensure that the correct IAM permissions are added
        at the aws.S3AccessPolicy level.
        """
        paths = self.cleaned_data["paths"]
        for path in paths:
            if not path.startswith("/"):
                raise ValidationError("Enter paths prefixed with a forward slash")

            if path.endswith("/"):
                raise ValidationError("Enter paths without a trailing forward slash")

        return paths


class TableGrantAccessForm(forms.Form):
    access_level = forms.ChoiceField(
        choices=[("readonly", "Read Only")],
        required=True,
    )
    entity_id = forms.CharField(max_length=128)

    def clean_entity_id(self):
        entity_id = self.cleaned_data["entity_id"]
        user = User.objects.filter(auth0_id=entity_id).first()

        if not user:
            raise ValidationError(f"User {entity_id} does not exist")

        return user

    def clean(self):

        permissions = {
            "readonly": {"resource_link": ["DESCRIBE"], "table": ["SELECT"]},
        }

        cleaned_data = super().clean()
        access_level = cleaned_data.get("access_level")
        cleaned_data["access_level"] = permissions[access_level]
        cleaned_data["user"] = cleaned_data.get("entity_id")

        return cleaned_data


class GrantAppAccessForm(forms.Form):
    access_level = forms.ChoiceField(
        choices=[
            ("readonly", "Read only"),
            ("readwrite", "Read/write"),
        ],
    )
    datasource = DatasourceChoiceField(
        empty_label="Select data source",
        queryset=S3Bucket.objects.none(),
    )

    def __init__(self, *args, **kwargs):
        self.app = kwargs.pop("app")
        self.user = kwargs.pop("user")
        self.exclude_connected = kwargs.pop("exclude_connected", True)

        super().__init__(*args, **kwargs)

        self.fields["datasource"].queryset = self.get_datasource_queryset()

    def get_datasource_queryset(self):
        """
        For all users excludes deleted buckets
        Optionally excludes connected buckets
        If the user is a superuser, returns all remaining buckets
        Otherwise, returns only non-data warehouse buckets that the user has access to
        """
        queryset = S3Bucket.objects.filter(is_deleted=False)
        if self.exclude_connected:
            queryset = queryset.exclude(
                pk__in=self.app.apps3buckets.values_list("s3bucket__pk", flat=True)
            )

        if self.user.is_superuser:
            return queryset

        return queryset.filter(
            users3buckets__in=self.user.users3buckets.filter(is_admin=True),
            is_data_warehouse=False,
        )


class GrantDomainAccessForm(forms.Form):

    whitelist_domain = DatasourceChoiceField(
        empty_label="Select domain",
        queryset=DashboardDomain.objects.none(),
    )

    def __init__(self, *args, **kwargs):
        self.dashboard = kwargs.pop("dashboard")
        self.exclude_connected = kwargs.pop("exclude_connected", True)

        super().__init__(*args, **kwargs)

        self.fields["whitelist_domain"].queryset = self.get_datasource_queryset()

    def get_datasource_queryset(self):
        """
        Get all domains except those that are already assigned to the dashboard
        """
        queryset = DashboardDomain.objects.all()
        if self.exclude_connected:
            queryset = queryset.exclude(
                pk__in=self.dashboard.whitelist_domains.values_list("id", flat=True)
            )

        return queryset


class CreateIAMManagedPolicyForm(forms.Form):
    name = forms.CharField(
        # TODO restrict allowed characters in group policy name
        validators=[RegexValidator(POLICY_NAME_REGEX)]
    )


class AddUserToIAMManagedPolicyForm(forms.Form):
    user_id = forms.CharField(max_length=128)


class CustomersField(forms.Field):
    def __init__(self, *, delimiters=CUSTOMERS_DELIMITERS, strip=True, **kwargs):
        self.delimiters = delimiters
        self.strip = strip
        super().__init__(**kwargs)

    def to_python(self, value):
        emails = self.delimiters.split(value)
        if self.strip:
            emails = [email.strip() for email in emails]
        return emails

    def clean(self, value):
        value = self.to_python(value)
        for email in value:
            try:
                validate_email(email)
            except ValidationError:
                raise ValidationError(
                    '"%(value)s" is not a valid email address',
                    params={"value": email},
                )
        return value


class AddCustomersForm(forms.Form):
    customer_email = CustomersField()

    def clean_customer_email(self):
        return [email.lower() for email in self.cleaned_data["customer_email"]]


class RemoveCustomerByEmailForm(forms.Form):
    prefix = "remove"

    email = forms.EmailField(widget=forms.EmailInput(attrs={"class": "govuk-input cpanel-input"}))


class ResetHomeDirectoryForm(forms.Form):
    confirm = forms.BooleanField(
        required=True,
        help_text="I confirm that I want to reset my home directory.",
        widget=forms.CheckboxInput(attrs={"class": "govuk-checkboxes__input"}),
    )


class ToolReleaseForm(forms.ModelForm):
    target_users_list = forms.CharField(required=False)

    def clean_target_users_list(self):
        target_users_list = self.cleaned_data["target_users_list"]
        if not target_users_list:
            return target_users_list

        target_users_list = set(
            [username.strip().lower() for username in target_users_list.split(",")]
        )

        found_users = User.objects.filter(username__in=target_users_list)
        not_found_users = set(target_users_list) - set(
            found_users.values_list("username", flat=True)
        )
        if not_found_users:
            raise ValidationError(f"Users not found: {', '.join(not_found_users)}")
        return found_users

    def clean_chart_name(self):
        """
        Ensures that the helm chart name entered by the user is a valid one.

        Why not use a "choice" argument in the Tool model's class? It would
        result in a new Django migration for the database to enforce this (and
        we'd have to keep adding new migrations to the database every time we
        created a new helm chart for a new tool). Furthermore, the HTML select
        field we'd use in the form isn't supported in the macros we use.

        Hence the path of least resistance with this custom form validation.
        """
        valid_charts = ["airflow-sqlite", "jupyter-", "rstudio", "vscode"]
        value = self.cleaned_data["chart_name"]
        is_valid = False
        for chart_name in valid_charts:
            if chart_name in value:
                is_valid = True
                break
        if not is_valid:
            raise ValidationError(
                f"'{value}' is not a valid helm chart name. ",
            )
        return value

    def clean_tool_domain(self):
        """
        Ensures that if the bespoke tool_domain value is specified it is ONLY
        one of the acceptable names.
        """
        valid_names = ["airflow-sqlite", "jupyter-lab", "rstudio", "vscode"]
        value = self.cleaned_data.get("tool_domain")
        if value and value not in valid_names:
            raise ValidationError(
                f"'{value}' is not a valid tool domain value. ",
            )
        return value

    class Meta:
        model = Tool
        fields = [
            "name",
            "chart_name",
            "version",
            "image_tag",
            "values",
            "is_restricted",
            "tool_domain",
            "description",
            "is_deprecated",
            "deprecated_message",
            "is_retired",
        ]


class AppSecretForm(forms.Form):
    key = forms.CharField(
        validators=[
            RegexValidator(
                r"[a-zA-Z0-9_]",
                message=("Must contain only alphanumeric characters and underscores"),
            ),
        ],
    )
    env_name = forms.CharField(widget=forms.HiddenInput)
    value = forms.CharField(
        max_length=65536,
        widget=forms.PasswordInput(attrs={"class": "govuk-input cpanel-input--1-3"}),
    )


class AppSecretUpdateForm(AppSecretForm):
    key = forms.CharField(widget=forms.HiddenInput)
    display_key = forms.CharField(widget=forms.HiddenInput)


class AppVariableForm(AppSecretForm):
    value = forms.CharField(max_length=65536)


class AppVariableUpdateForm(AppVariableForm):
    key = forms.CharField(widget=forms.HiddenInput)
    display_key = forms.CharField(widget=forms.HiddenInput)


class DisableAuthForm(AppVariableUpdateForm):
    value = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={"class": "govuk-checkboxes__input"}),
        help_text="Require authentication for your app",
    )

    def __init__(self, *args, **kwargs):
        init_for_value = kwargs.get("initial", {}).get("value")
        kwargs["initial"]["value"] = str(init_for_value or "true").lower() == "true"
        super(DisableAuthForm, self).__init__(*args, **kwargs)


class IPAllowlistForm(forms.ModelForm):
    class Meta:
        model = IPAllowlist
        fields = [
            "name",
            "description",
            "contact",
            "allowed_ip_ranges",
            "is_recommended",
        ]


class CreateParameterForm(forms.Form):
    key = forms.CharField(
        max_length=50,
        validators=[
            RegexValidator(
                r"[a-zA-Z0-9_]{1,50}",
                message=(
                    "Must be 50 characters or fewer and contain only alphanumeric "
                    "characters and underscores"
                ),
            ),
        ],
    )
    role_name = forms.CharField(
        max_length=60,
        validators=[
            RegexValidator(
                r"[a-zA-Z0-9_-]{1,60}",
                message=(
                    "Must be 60 characters or fewer and contain only alphanumeric "
                    "characters, underscores and hyphens"
                ),
            ),
        ],
    )
    value = forms.CharField(widget=forms.PasswordInput)


class QuicksightAccessForm(forms.Form):
    QUICKSIGHT_COMPUTE_AUTHOR = "quicksight_compute_author"
    QUICKSIGHT_COMPUTE_READER = "quicksight_compute_reader"

    enable_quicksight = forms.MultipleChoiceField(
        choices=[
            (QUICKSIGHT_COMPUTE_AUTHOR, "Author"),
            (QUICKSIGHT_COMPUTE_READER, "Reader"),
        ],
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )

    quicksight_config_data = {
        QUICKSIGHT_COMPUTE_AUTHOR: {
            "codename": QUICKSIGHT_EMBED_AUTHOR_PERMISSION,
            "group": settings.QUICKSIGHT_AUTHOR_GROUP_NAME,
        },
        QUICKSIGHT_COMPUTE_READER: {
            "codename": QUICKSIGHT_EMBED_READER_PERMISSION,
            "group": settings.QUICKSIGHT_READER_GROUP_NAME,
        },
    }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user")
        super().__init__(*args, **kwargs)

    def grant_access(self):
        quicksight_access = self.cleaned_data["enable_quicksight"]

        self.set_quicksight_embed_access(self.QUICKSIGHT_COMPUTE_AUTHOR, quicksight_access)
        self.set_quicksight_embed_access(self.QUICKSIGHT_COMPUTE_READER, quicksight_access)

    def set_quicksight_embed_access(self, permission_name, quicksight_access):
        identity_store = AWSIdentityStore(
            settings.IDENTITY_CENTER_ASSUMED_ROLE,
            "APCPIdentityCenterAccess",
            settings.IDENTITY_CENTER_ACCOUNT_REGION,
        )
        if self.user.is_superuser:
            return

        codename = self.quicksight_config_data.get(permission_name)["codename"]
        group = self.quicksight_config_data.get(permission_name)["group"]
        permission = Permission.objects.get(codename=codename)

        if permission_name in quicksight_access and not self.user.has_perm(f"api.{codename}"):
            identity_store.add_user_to_group(self.user.justice_email, group)
            self.user.user_permissions.add(permission)
        elif permission_name not in quicksight_access and self.user.has_perm(f"api.{codename}"):
            identity_store.delete_group_membership(self.user.justice_email, group)
            self.user.user_permissions.remove(permission)


class AdminQuicksightAccessForm(QuicksightAccessForm):
    QUICKSIGHT_LEGACY = "quicksight_legacy"

    enable_quicksight = forms.MultipleChoiceField(
        choices=[
            (QUICKSIGHT_LEGACY, "Legacy"),
            (QuicksightAccessForm.QUICKSIGHT_COMPUTE_AUTHOR, "Author"),
            (QuicksightAccessForm.QUICKSIGHT_COMPUTE_READER, "Reader"),
        ],
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )

    def grant_access(self):
        quicksight_access = self.cleaned_data["enable_quicksight"]
        self.user.set_quicksight_access(enable=self.QUICKSIGHT_LEGACY in quicksight_access)

        self.set_quicksight_embed_access(self.QUICKSIGHT_COMPUTE_AUTHOR, quicksight_access)
        self.set_quicksight_embed_access(self.QUICKSIGHT_COMPUTE_READER, quicksight_access)


class FeedbackForm(forms.ModelForm):
    class Meta:
        model = Feedback
        fields = [
            "satisfaction_rating",
            "suggestions",
        ]


class RegisterDashboardForm(forms.ModelForm):

    class Meta:
        model = Dashboard
        fields = [
            "name",
            "quicksight_id",
        ]

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user")
        super().__init__(*args, **kwargs)

    def clean_quicksight_id(self):
        dashboard_url = self.cleaned_data["quicksight_id"]

        prefix = (
            f"https://{settings.QUICKSIGHT_ACCOUNT_REGION}.quicksight.aws.amazon.com/sn/dashboards/"
        )
        if not dashboard_url.startswith(prefix):
            raise ValidationError("The URL entered is not a valid QuickSight dashboard URL")

        quicksight_id = dashboard_url.split(prefix)[1]
        if not quicksight_id:
            raise ValidationError("The URL entered is not a valid QuickSight dashboard URL")

        if not AWSQuicksight().has_update_dashboard_permissions(
            dashboard_id=quicksight_id, user=self.user
        ):
            raise ValidationError("You do not have permission to register this dashboard")

        existing_dashboard = Dashboard.objects.filter(quicksight_id=quicksight_id).first()
        if existing_dashboard:
            raise ValidationError(
                f"This dashboard is already registered by {existing_dashboard.created_by.justice_email}. Please contact them to request access."  # noqa
            )

        return quicksight_id


class ToolChoice(forms.Select):

    def __init__(self, user=None, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):

        option = super().create_option(name, value, label, selected, index, subindex, attrs)
        if value:
            option["attrs"]["data-is-deprecated"] = f"{value.instance.is_deprecated}"
            option["attrs"]["data-deprecated-message"] = value.instance.get_deprecated_message
            option["attrs"]["data-tool-url"] = build_tool_url(tool=value.instance, user=self.user)

        if value and selected:
            option["attrs"]["label"] = f"{label} (installed)"
            option["attrs"]["class"] = "installed"

        return option


class ToolDeploymentForm(forms.Form):

    tool = forms.ModelChoiceField(
        queryset=Tool.objects.none(),
        empty_label='Select a tool from this list and click "Deploy" to start',
    )

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user")
        self.tool_type = kwargs.pop("tool_type")
        self.deployment = kwargs.pop("deployment", None)
        super().__init__(*args, **kwargs)
        self.fields["tool"].widget = ToolChoice(
            user=self.user,
            attrs={
                "class": "govuk-select govuk-!-width-full govuk-!-font-size-16",
                "data-action-target": self.tool_type,
                "id": f"tools-{self.tool_type}",
            },
        )
        self.fields["tool"].queryset = self.get_tool_release_choices(tool_type=self.tool_type)
        if self.deployment:
            self.fields["tool"].initial = self.deployment.tool

    def get_tool_release_choices(self, tool_type: str):
        """
        Return a queryset for Tool objects where:

        * The tool is not retired

        AND EITHER:

        * The tool is not restricted

        OR

        * The current user has access to the restricted tool
        """
        return (
            Tool.objects.filter(
                Q(is_restricted=False) | Q(target_users=self.user),
                chart_name__startswith=tool_type,
            )
            .exclude(is_retired=True)
            .order_by("-chart_name", "-image_tag", "-version", "-created")
            .distinct()
        )

    @property
    def tool_type_label(self):
        return ToolDeployment.ToolType(self.tool_type).label

    @property
    def tool_url(self):
        return self.deployment.url if self.deployment else ""


class ToolDeploymentRestartForm(forms.Form):
    tool_deployment = forms.ModelChoiceField(queryset=ToolDeployment.objects.none())

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user")
        super().__init__(*args, **kwargs)
        self.fields["tool_deployment"].queryset = self.user.tool_deployments.active()
