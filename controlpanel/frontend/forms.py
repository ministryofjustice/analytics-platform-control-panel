import re

from django import forms
from django.conf import settings
from django.contrib.postgres.forms import SimpleArrayField
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator, validate_email

from controlpanel.api import validators
from controlpanel.api.cluster import get_repository
from controlpanel.api.models import App, S3Bucket, Tool, User
from controlpanel.api.models.access_to_s3bucket import S3BUCKET_PATH_REGEX
from controlpanel.api.models.iam_managed_policy import POLICY_NAME_REGEX
from controlpanel.api.models.parameter import APP_TYPE_CHOICES


APP_CUSTOMERS_DELIMITERS = re.compile(r'[,; ]+')


class DatasourceChoiceField(forms.ModelChoiceField):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.widget.attrs['class'] = 'govuk-select govuk-!-width-one-half'

    def label_from_instance(self, instance):
        return instance.name


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
        ],
        required=False,
    )
    existing_datasource_id = DatasourceChoiceField(
        queryset=S3Bucket.objects.filter(is_data_warehouse=False),
        empty_label="Select",
        required=False,
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

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        connect = cleaned_data['connect_bucket']
        new_datasource = cleaned_data.get('new_datasource_name')
        existing_datasource = cleaned_data.get('existing_datasource_id')

        if connect == "new":
            if new_datasource:
                try:
                    S3Bucket.objects.get(name=new_datasource)
                    self.add_error(
                        "new_datasource_name",
                        f"Datasource named {new_datasource} already exists"
                    )
                except S3Bucket.DoesNotExist:
                    pass

            else:
                self.add_error('new_datasource_name', "This field is required.")

        if connect == "existing" and not existing_datasource:
            self.add_error('existing_datasource_id', "This field is required.")

        return cleaned_data

    def clean_repo_url(self):
        value = self.cleaned_data['repo_url']
        repo_name = value.replace("https://github.com/", "", 1)
        repo = get_repository(self.request.user, repo_name)
        if repo is None:
            raise ValidationError(
                f"Github repository not found - it may be private",
            )

        if App.objects.filter(repo_url=value).exists():
            raise ValidationError(f"App already exists for this repository URL")

        return value


class CreateDatasourceForm(forms.Form):
    name = forms.CharField(
        max_length=63,
        validators=[
            validators.validate_env_prefix,
            validators.validate_s3_bucket_labels,
            validators.validate_s3_bucket_length,
        ],
    )


class GrantAccessForm(forms.Form):
    access_level = forms.ChoiceField(
        choices=[
            ("readonly", "Read only"),
            ("readwrite", "Read/write"),
            ("admin", "Admin"),
        ],
        required=True
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
            "for whole bucket access"
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
        access_level = cleaned_data.get('access_level')
        if access_level == 'admin':
            cleaned_data['access_level'] = 'readwrite'
            cleaned_data['is_admin'] = True

        if cleaned_data["entity_type"] == "user":
            cleaned_data['user_id'] = cleaned_data["entity_id"]
        elif cleaned_data["entity_type"] == "group":
            cleaned_data['policy_id'] = cleaned_data["entity_id"]

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
        self.app = kwargs.pop('app')
        self.exclude_connected = kwargs.pop('exclude_connected', False)

        super().__init__(*args, **kwargs)

        if self.exclude_connected:
            self.fields['datasource'].queryset = S3Bucket.objects.exclude(
                id__in=[a.s3bucket_id for a in self.app.apps3buckets.all()],
            )
        else:
            self.fields['datasource'].queryset = S3Bucket.objects.all()


class CreateParameterForm(forms.Form):
    key = forms.CharField(
        max_length=50,
        validators=[
            RegexValidator(
                r'[a-zA-Z0-9_]{1,50}',
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
                r'[a-zA-Z0-9_-]{1,60}',
                message=(
                    "Must be 60 characters or fewer and contain only alphanumeric "
                    "characters, underscores and hyphens"
                ),
            ),
        ],
    )
    value = forms.CharField(widget=forms.PasswordInput)
    app_type = forms.ChoiceField(choices=APP_TYPE_CHOICES)


class CreateIAMManagedPolicyForm(forms.Form):
    name = forms.CharField(
        # TODO restrict allowed characters in group policy name
        validators=[RegexValidator(POLICY_NAME_REGEX)]
    )


class AddUserToIAMManagedPolicyForm(forms.Form):
    user_id = forms.CharField(max_length=128)


class AppCustomersField(forms.Field):

    def __init__(self, *, delimiters=APP_CUSTOMERS_DELIMITERS, strip=True, **kwargs):
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
                    params={'value': email},
                )
        return value


class AddAppCustomersForm(forms.Form):
    customer_email = AppCustomersField()



class ResetHomeDirectoryForm(forms.Form):
    confirm = forms.BooleanField(
        required=True,
        help_text="I confirm that I want to reset my home directory.",
        widget=forms.CheckboxInput(attrs={"class": "govuk-checkboxes__input"})
    )


class ToolReleaseForm(forms.ModelForm):
    target_users_list = forms.CharField(required=False)

    def get_target_users(self):
        """
        Returns a collection of User instances of those users who are marked as
        having access to the restricted release.
        """
        target_list = self.data.get("target_users_list", "")
        if target_list:
            usernames = set([
                username.strip() for username in target_list.split(",")
            ])
            return User.objects.filter(username__in=usernames)
        else:
            return []

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
        valid_charts = ["airflow-sqlite", "jupyter-", "rstudio", ]
        value = self.cleaned_data['chart_name']
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
        valid_names = ["airflow-sqlite", "jupyter-lab", "rstudio", ]
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
            "values",
            "is_restricted",
            "target_infrastructure",
            "tool_domain",
        ]
