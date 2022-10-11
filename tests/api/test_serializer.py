# Third-party
import pytest

# First-party/Local
from controlpanel.api.serializers import ParameterSecretSerializer


@pytest.mark.parametrize(
    "name, items, expected, error_num",
    [
        ("hell-~o", {}, False, 1),
        ("hello-world", {}, False, 1),
        ("valid_key", {}, True, 0),
    ],
)
def test_secret_parameter_name(name, items, expected, error_num):
    serial = ParameterSecretSerializer(data=dict(app_name_unique=name, **items))
    assert serial.is_valid() == expected
    assert len(serial.errors) == error_num


@pytest.mark.parametrize(
    "data_dump, is_valid, result_data, error_num",
    [
        (
            dict(environment="alpha", deployment="auto"),
            True,
            dict(environment="alpha", deployment="auto"),
            0,
        ),
        (
            dict(environment="alpha", deployment="auto"),
            True,
            dict(environment="alpha", deployment="auto"),
            0,
        ),
        (
            dict(environment="alpha", deployment="auto"),
            True,
            dict(environment="alpha", deployment="auto"),
            0,
        ),
        ({"environment": "alpha", "deplo--yment": "auto"}, False, {}, 1),
    ],
)
def test_key_value_to_serial(data_dump, is_valid, result_data, error_num):
    serial = ParameterSecretSerializer(data=data_dump)
    assert serial.is_valid() == is_valid
    assert serial.data == result_data
    assert len(serial.errors) == error_num
