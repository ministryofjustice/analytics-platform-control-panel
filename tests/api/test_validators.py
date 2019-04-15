from django.core.exceptions import ValidationError
import pytest

from controlpanel.api import validators


def test_validate_env_prefix():
    with pytest.raises(ValidationError):
        validators.validate_env_prefix('foo-bucketname')

    validators.validate_env_prefix('test-bucketname')
