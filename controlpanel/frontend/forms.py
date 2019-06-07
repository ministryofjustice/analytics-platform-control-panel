from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
import requests

from controlpanel.api import validators
from controlpanel.api.models import S3Bucket


def validate_github_repo_url(value):
    github_base_url = "https://github.com/"

    if not value.startswith(github_base_url):
        raise ValidationError("Invalid Github repository URL")

    repo_name = value[len(github_base_url):]
    org, repo = repo_name.split("/", 1)

    if org not in settings.GITHUB_ORGS:
        orgs = ", ".join(settings.GITHUB_ORGS)
        raise ValidationError(
            f"Unknown Github organization, must be one of {orgs}",
        )

    r = requests.head(f"https://api.github.com/repos/{repo_name}")
    if r.status_code != 200:
        raise ValidationError(
            f"Github repository not found - it may be private",
        )


class DatasourceChoiceField(forms.ModelChoiceField):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.widget.attrs['class'] = 'govuk-select govuk-!-width-one-half'

    def label_from_instance(self, instance):
        return instance.name


class CreateAppForm(forms.Form):
    repo_url = forms.CharField(validators=[validate_github_repo_url])
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

    def clean(self):
        cleaned_data = super().clean()

        if cleaned_data['connect_bucket'] == "new" and not cleaned_data.get('new_datasource_name'):
            self.add_error('new_datasource_name', "This field is required.")

        if cleaned_data['connect_bucket'] == "existing" and not cleaned_data.get('existing_datasource_id'):
            self.add_error('existing_datasource_id', "This field is required.")

        return cleaned_data


class CreateDatasourceForm(forms.Form):
    name = forms.CharField(
        max_length=60,
        validators=[RegexValidator(r'[a-z0-9.-]{1,60}')],
    )


class GrantAccessForm(forms.Form):
    is_admin = forms.BooleanField(initial=False, required=False)
    user_id = forms.CharField(max_length=128)
    access_level = forms.ChoiceField(
        choices=[
            ("readonly", "Read only"),
            ("readwrite", "Read/write"),
            ("admin", "Admin"),
        ],
    )

    def clean(self):
        cleaned_data = super().clean()
        access_level = cleaned_data['access_level']
        if access_level == 'admin':
            cleaned_data['access_level'] = 'readwrite'
            cleaned_data['is_admin'] = True
        return cleaned_data


class GrantAppAccessForm(forms.Form):
    access_level = forms.ChoiceField(
        choices=[
            ("readonly", "Read only"),
            ("readwrite", "Read/write"),
        ],
    )

    def __init__(self, *args, **kwargs):
        app = kwargs.pop('app')
        super().__init__(*args, **kwargs)
        self.fields['datasource'] = DatasourceChoiceField(
            empty_label="Select data source",
            queryset=S3Bucket.objects.exclude(
                id__in=[a.s3bucket_id for a in app.apps3buckets.all()],
            ),
        )
