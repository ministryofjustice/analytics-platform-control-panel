from django.core.exceptions import ValidationError
from django.test.testcases import SimpleTestCase

from control_panel_api import validators


class ValidatorsTestCase(SimpleTestCase):
    def test_validate_env_prefix(self):
        with self.assertRaises(ValidationError):
            validators.validate_env_prefix('foo-bucketname')

        validators.validate_env_prefix('test-bucketname')
