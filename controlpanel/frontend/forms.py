from django import forms
from django.conf import settings
from django.contrib.postgres.forms import SimpleArrayField, SplitArrayField
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator

from controlpanel.api import validators
from controlpanel.api.cluster import get_repository
from controlpanel.api.models import S3Bucket
from controlpanel.api.models.parameter import APP_TYPE_CHOICES


class DatasourceChoiceField(forms.ModelChoiceField):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.widget.attrs['class'] = 'govuk-select govuk-!-width-one-half'

    def label_from_instance(self, instance):
        return instance.name


class CreateAppForm(forms.Form):
    repo_url = forms.CharField(max_length=512)
    connect_bucket = forms.ChoiceField(choices=[
        ("new", "new"),
        ("existing", "existing"),
        ("later", "later"),
    ])
    new_datasource_name = forms.CharField(
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

        if cleaned_data['connect_bucket'] == "new" and not cleaned_data.get('new_datasource_name'):
            self.add_error('new_datasource_name', "This field is required.")

        if cleaned_data['connect_bucket'] == "existing" and not cleaned_data.get('existing_datasource_id'):
            self.add_error('existing_datasource_id', "This field is required.")

        return cleaned_data

    def clean_repo_url(self):
        github_base_url = "https://github.com/"
        value = self.cleaned_data['repo_url']

        if not value.startswith(github_base_url):
            raise ValidationError("Invalid Github repository URL")

        repo_name = value[len(github_base_url):]
        org, _ = repo_name.split("/", 1)

        if org not in settings.GITHUB_ORGS:
            orgs = ", ".join(settings.GITHUB_ORGS)
            raise ValidationError(
                f"Unknown Github organization, must be one of {orgs}",
            )

        repo = get_repository(self.request.user, repo_name)
        if repo is None:
            raise ValidationError(
                f"Github repository not found - it may be private",
            )

        return value


def has_env_prefix(value):
    if not value.startswith(f'{settings.ENV}-'):
        raise ValidationError(
            f"Bucket name must be prefixed with {settings.ENV}-"
        )


class CreateDatasourceForm(forms.Form):
    name = forms.CharField(
        max_length=60,
        validators=[
            has_env_prefix,
            RegexValidator(r'[a-z0-9.-]{1,60}'),
        ],
    )


class GrantAccessBaseForm(forms.Form):
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
                RegexValidator(r'[a-zA-Z0-9_/\*-]'),
            ],
            required=True,
        ),
        label="Paths",
        help_text="Add specific paths for this user or group to access",
        required=False,
        delimiter="\n",
    )

    def clean(self):
        cleaned_data = super().clean()
        access_level = cleaned_data['access_level']
        if access_level == 'admin':
            cleaned_data['access_level'] = 'readwrite'
            cleaned_data['is_admin'] = True
        return cleaned_data


class GrantAccessForm(GrantAccessBaseForm):
    is_admin = forms.BooleanField(initial=False, required=False)
    user_id = forms.CharField(max_length=128)


class GrantIAMManagedPolicyAccessForm(GrantAccessBaseForm):
    policy_id = forms.IntegerField()


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
        validators=[RegexValidator(r'[a-zA-Z0-9_]{1,50}')]
    )
    role_name = forms.CharField(
        validators=[RegexValidator(r'[a-zA-Z0-9_-]{1,60}')]
    )
    value = forms.CharField(widget=forms.PasswordInput)
    app_type = forms.ChoiceField(choices=APP_TYPE_CHOICES)


class CreateIAMManagedPolicyForm(forms.Form):
    name = forms.CharField(
        validators=[RegexValidator(r'[a-zA-Z0-9_-]{1,60}')]
    )


class AddUserToIAMManagedPolicyForm(forms.Form):
    user_id = forms.CharField(max_length=128)
