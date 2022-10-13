# Third-party
import pytest
from pydantic import parse_obj_as

# First-party/Local
from controlpanel.api.serializers import SecretSerializer


@pytest.mark.parametrize(
    "items,error_num",
    [
        ({"hell-~o": "here"}, 1),
        ({"hello-world": "here"}, 1),
        ({"valid_key": "here"}, 0),
    ],
)
def test_secret_parameter_name(items, error_num):
    try:
        parse_obj_as(SecretSerializer, items)
        assert error_num == 0
    except Exception:
        assert error_num


@pytest.mark.parametrize(
    "data_dump,result_data,error_num",
    [
        (
            dict(environment="alpha", deployment="auto"),
            dict(environment="alpha", deployment="auto"),
            0,
        ),
        (
            dict(environment="alpha", deployment="auto"),
            dict(environment="alpha", deployment="auto"),
            0,
        ),
        (
            dict(environment="alpha", deployment="auto"),
            dict(environment="alpha", deployment="auto"),
            0,
        ),
        ({"environment": "alpha", "deplo--yment": "auto"}, {}, 1),
    ],
)
def test_key_value_to_serial(data_dump, result_data, error_num):
    try:
        serial = parse_obj_as(SecretSerializer, data_dump)
        assert serial.get_data() == result_data
        assert error_num == 0
    except Exception:
        assert error_num
