from django import forms
from django.core.validators import RegexValidator


class CreateDatasourceForm(forms.Form):
    name = forms.CharField(
        max_length=60,
        validators=[RegexValidator(r'[a-z0-9.-]{1,60}')],
    )
