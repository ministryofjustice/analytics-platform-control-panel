from django import forms
from django.core.validators import RegexValidator


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
