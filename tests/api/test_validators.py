from django.core.exceptions import ValidationError
import pytest

from controlpanel.api import validators


def test_validate_env_prefix():
    with pytest.raises(ValidationError):
        validators.validate_env_prefix('foo-bucketname')

    validators.validate_env_prefix('test-bucketname')

@pytest.mark.parametrize(
    "ip_ranges_text, ip_error",
    [("not an ip address", r"not an ip address"),
     ("123, 456", r"123"),
     ("192.168.0.0/28 192.168.0.1", r"192.168.0.0/28 192.168.0.1"),
     ("192.168.0.0.0", r"192.168.0.0.0")]
)
def test_validate_ip_ranges_fail(ip_ranges_text, ip_error):
    with pytest.raises(ValidationError, match=ip_error):
        validators.validate_ip_ranges(ip_ranges_text)

@pytest.mark.parametrize(
    "ip_ranges_text",
    ["192.168.0.0/28",
     "192.168.0.0/28, 192.168.0.1",
     "192.168.0.0/28 , 192.168.0.1"]
)
def test_validate_ip_ranges_pass(ip_ranges_text):
    validators.validate_ip_ranges(ip_ranges_text)
