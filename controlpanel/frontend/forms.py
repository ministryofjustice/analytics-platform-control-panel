from django import forms
from django.conf import settings
from django.contrib.postgres.forms import SimpleArrayField
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator

from controlpanel.api import validators
from controlpanel.api.cluster import get_repository
from controlpanel.api.models import App, S3Bucket
from controlpanel.api.models.access_to_s3bucket import S3BUCKET_PATH_REGEX
from controlpanel.api.models.iam_managed_policy import POLICY_NAME_REGEX
from controlpanel.api.models.parameter import APP_TYPE_CHOICES


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
    connect_bucket = forms.ChoiceField(choices=[
        ("new", "new"),
        ("existing", "existing"),
        ("later", "later"),
    ])
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

        try:
            app = App.objects.get(repo_url=value)
            raise ValidationError(f"App already exists for this repository URL")
        except App.DoesNotExist:
            pass

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
        access_level = cleaned_data['access_level']
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
                message="Must contain only alphanumeric characters and underscores",
            ),
        ],
    )
    role_name = forms.CharField(
        max_length=60,
        validators=[
            RegexValidator(
                r'[a-zA-Z0-9_-]{1,60}',
                message="Must contain only alphanumeric characters, underscores and hyphens",
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
