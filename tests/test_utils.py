import pytest

from django.conf import settings
from controlpanel.utils import SettingLoader


def test_not_overwrite_var_in_setting():
    test_json={
        "AWS_COMPUTE_ACCOUNT_ID": "new_account_id"
    }
    SettingLoader(test_json)
    assert settings.AWS_COMPUTE_ACCOUNT_ID == "test_compute_account_id"


def test_add_new_var_in_setting():
    assert not hasattr(settings, "NEW_TESTING_SET")
    test_json={
        "NEW_TESTING_SET": "I am new"
    }
    SettingLoader(test_json)
    assert hasattr(settings, "NEW_TESTING_SET")
    assert settings.NEW_TESTING_SET == test_json["NEW_TESTING_SET"]


def test_feature_flag_default_true():
    test_json={
        "enabled_features": {
            "test_feature": {
                "_DEFAULT": True
            }
        }
    }
    SettingLoader(test_json)
    assert settings.features.test_feature.enabled


def test_feature_flag_default_false():
    test_json={
        "enabled_features": {
            "test_feature": {
                "_DEFAULT": False
            }
        }
    }
    SettingLoader(test_json)
    assert not settings.features.test_feature.enabled


def test_feature_flag_env_false():
    test_json={
        "enabled_features": {
            "test_feature": {
                "_DEFAULT": True,
                "_HOST_test": False
            }
        }
    }
    SettingLoader(test_json)
    assert not settings.features.test_feature.enabled


def test_feature_flag_env_True():
    test_json={
        "enabled_features": {
            "test_feature": {
                "_DEFAULT": False,
                "_HOST_test": True
            }
        }
    }
    SettingLoader(test_json)
    assert settings.features.test_feature.enabled
