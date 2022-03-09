import io
import sys
import uuid

from django.core.management import call_command
from django.core.management.base import CommandError
from unittest.mock import MagicMock, patch

from controlpanel.api.auth0 import ManagementAPI
from controlpanel.api.models import App
from controlpanel.cli.management.commands.add_app_user import Command

import pytest


TEST_APP_NAME = "an-app"
TEST_EMAIL = "test-user@justice.gov.uk"


@pytest.fixture
def new_app(db) -> App:
    return App.objects.create(
        slug=TEST_APP_NAME,
        repo_url=f"https://github.com/moj-analytical-services/{TEST_APP_NAME}",
    )


@pytest.mark.indevelopment
@pytest.mark.django_db
class TestAddingAppUsers(object):
    def invoke(self, email: str = "", app: str = ""):
        buffer = io.StringIO()
        stdout = sys.stdout

        try:
            sys.stdout = buffer
            call_command("add_app_user", email=email, app=app)
        finally:
            sys.stdout = stdout

        return buffer.getvalue()

    def test_new_user_missing_app(self):
        with pytest.raises(CommandError) as e:
            _output = self.invoke(email="", app="no-existy")
            assert e.message == "This app does not exist"

    def test_invalid_user_existing_app(self, new_app):
        with pytest.raises(CommandError) as e:
            _output = self.invoke(email="", app=TEST_APP_NAME)
            assert (
                e.message
                == "Extensive parsing has determined the user's email is not valid"
            )

    def test_existing_user_existing_app(self, new_app):
        # Search finds the appropriate user ...
        ManagementAPI.get_users_email_search = MagicMock(
            return_value=[{"email": TEST_EMAIL, "user_id": "12345"}]
        )

        _output = self.invoke(email=TEST_EMAIL, app=TEST_APP_NAME)
        ManagementAPI.get_users_email_search.assert_called_with(
            TEST_EMAIL, connection="email"
        )

    def test_new_user_existing_app(self, new_app):
        # Search finds no user so we create a new one
        ManagementAPI.get_users_email_search = MagicMock(return_value=[])
        ManagementAPI.create_user = MagicMock(
            return_value=[{"email": TEST_EMAIL, "user_id": "12345"}]
        )

        _output = self.invoke(email=TEST_EMAIL, app=TEST_APP_NAME)
        ManagementAPI.get_users_email_search.assert_called_with(
            TEST_EMAIL, connection="email"
        )
