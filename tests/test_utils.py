# Third-party
from django import forms
from django.conf import settings

# First-party/Local
from controlpanel.frontend.forms import ErrorSummaryMixin, MultiEmailField
from controlpanel.utils import SettingLoader


def test_not_overwrite_var_in_setting():
    test_json = {"AWS_DATA_ACCOUNT_ID": "new_account_id"}
    SettingLoader(test_json)
    assert settings.AWS_DATA_ACCOUNT_ID == "123456789012"


def test_add_new_var_in_setting():
    assert not hasattr(settings, "NEW_TESTING_SET")
    test_json = {"NEW_TESTING_SET": "I am new"}
    SettingLoader(test_json)
    assert hasattr(settings, "NEW_TESTING_SET")
    assert settings.NEW_TESTING_SET == test_json["NEW_TESTING_SET"]


def test_feature_flag_default_true():
    test_json = {"enabled_features": {"test_feature": {"_DEFAULT": True}}}
    SettingLoader(test_json)
    assert settings.features.test_feature.enabled


def test_feature_flag_default_false():
    test_json = {"enabled_features": {"test_feature": {"_DEFAULT": False}}}
    SettingLoader(test_json)
    assert not settings.features.test_feature.enabled


def test_feature_flag_env_false():
    test_json = {"enabled_features": {"test_feature": {"_DEFAULT": True, "_HOST_test": False}}}
    SettingLoader(test_json)
    assert not settings.features.test_feature.enabled


def test_feature_flag_env_True():
    test_json = {"enabled_features": {"test_feature": {"_DEFAULT": False, "_HOST_test": True}}}
    SettingLoader(test_json)
    assert settings.features.test_feature.enabled


class TestErrorSummaryMixin:
    """Tests for the ErrorSummaryMixin form mixin."""

    def test_returns_empty_dict_for_valid_form(self):
        """Valid forms should return an empty error summary."""

        class SimpleForm(ErrorSummaryMixin, forms.Form):
            name = forms.CharField()

        form = SimpleForm(data={"name": "test"})
        assert form.is_valid()
        assert form.get_error_summary() == {}

    def test_returns_standard_errors(self):
        """Standard field errors should be returned with field name as key."""

        class SimpleForm(ErrorSummaryMixin, forms.Form):
            name = forms.CharField(required=True)

        form = SimpleForm(data={})
        assert not form.is_valid()

        result = form.get_error_summary()
        assert "id_name" in result
        assert "This field is required." in result["id_name"]

    def test_handles_index_errors_from_multi_email_field(self):
        """MultiEmailField index_errors should expand to indexed field keys."""

        class EmailForm(ErrorSummaryMixin, forms.Form):
            emails = MultiEmailField(required=True)

        form = EmailForm(data={"emails[0]": "valid@example.com", "emails[1]": "invalid"})
        assert not form.is_valid()

        result = form.get_error_summary()
        # Should have the invalid email at index 1
        assert "id_emails[1]" in result
        assert "Enter a valid email address" in result["id_emails[1]"]
        # Should NOT have a separate entry for the valid email
        assert "id_emails[0]" not in result

    def test_deduplicates_error_messages(self):
        """Same error message should only appear once in summary."""

        class EmailForm(ErrorSummaryMixin, forms.Form):
            emails = MultiEmailField(required=True)

        # Two invalid emails should only produce one error message in summary
        form = EmailForm(data={"emails[0]": "invalid1", "emails[1]": "invalid2"})
        assert not form.is_valid()

        result = form.get_error_summary()
        # First invalid email gets the error
        assert "id_emails[0]" in result
        # Second invalid email is deduplicated (same message)
        assert "id_emails[1]" not in result

    def test_form_level_errors_point_to_first_indexed_field(self):
        """Form-level errors for indexed fields should point to first input."""

        class EmailForm(ErrorSummaryMixin, forms.Form):
            emails = MultiEmailField(required=True)

            def clean_emails(self):
                emails = self.cleaned_data.get("emails", [])
                if emails and "admin@test.com" in emails:
                    raise forms.ValidationError("Admin email not allowed")
                return emails

        form = EmailForm(data={"emails[0]": "admin@test.com"})
        assert not form.is_valid()

        result = form.get_error_summary()
        # Form-level validation error should point to id_emails[0]
        assert "id_emails[0]" in result
        assert "Admin email not allowed" in result["id_emails[0]"]

    def test_multiple_fields_with_different_errors(self):
        """Multiple fields with different errors should all be included."""

        class MultiFieldForm(ErrorSummaryMixin, forms.Form):
            name = forms.CharField(required=True, error_messages={"required": "Name is required"})
            email = forms.EmailField(
                required=True, error_messages={"required": "Email is required"}
            )

        form = MultiFieldForm(data={})
        assert not form.is_valid()

        result = form.get_error_summary()
        assert "id_name" in result
        assert "Name is required" in result["id_name"]
        assert "id_email" in result
        assert "Email is required" in result["id_email"]
