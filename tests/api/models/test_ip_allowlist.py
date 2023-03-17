# Standard library
from unittest.mock import call, patch

# Third-party
import pytest
from model_mommy import mommy


@pytest.fixture(autouse=True)
def enable_db_access_for_all_tests(db):
    pass


@pytest.yield_fixture
def update_aws_secrets_manager():
    with patch(
        "controlpanel.api.cluster.App.create_or_update_secret"
    ) as update_aws_secrets_manager:
        yield update_aws_secrets_manager


# def test_ip_allowlist_save_updates_aws_secrets_manager(update_aws_secrets_manager):
#     ip_allowlist = mommy.make("api.IPAllowlist", allowed_ip_ranges="123")
#     app = mommy.make("api.App", ip_allowlists=[ip_allowlist])  # noqa:F841
#
#     ip_allowlist.save()
#
#     update_aws_secrets_manager.assert_has_calls(
#         [
#             call({"allowed_ip_ranges": "123"}),
#         ]
#     )
#

def test_ip_allowlist_without_app_save_does_not_update_aws_secrets_manager(
    update_aws_secrets_manager,
):
    ip_allowlist = mommy.make("api.IPAllowlist")

    ip_allowlist.save()

    update_aws_secrets_manager.assert_not_called()


# def test_ip_allowlist_delete_updates_aws_secrets_manager(update_aws_secrets_manager):
#     ip_allowlists = [
#         mommy.make("api.IPAllowlist", allowed_ip_ranges="xyz"),
#         mommy.make("api.IPAllowlist", allowed_ip_ranges="123"),
#     ]
#     apps = mommy.make("api.App", ip_allowlists=ip_allowlists, _quantity=2)  # noqa:F841
#
#     ip_allowlists[0].delete()
#
#     update_aws_secrets_manager.assert_has_calls(
#         [call({"allowed_ip_ranges": "123"}), call({"allowed_ip_ranges": "123"})]
#     )
#

def test_ip_allowlist_without_app_delete_does_not_update_aws_secrets_manager(
    update_aws_secrets_manager,
):
    ip_allowlist = mommy.make("api.IPAllowlist")

    ip_allowlist.delete()

    update_aws_secrets_manager.assert_not_called()
