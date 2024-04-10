# Third-party
import pytest
from authlib.integrations.base_client import OAuthError
from django.urls import reverse, reverse_lazy
from unittest.mock import patch
from pytest_django.asserts import assertContains


class TestEntraIdAuthView:
    url = reverse_lazy("entraid-auth")

    def test_unauthorised(self, client):
        response = client.get(self.url)

        assert response.status_code == 302

    @patch("django.conf.settings.features.justice_auth.enabled", False)
    def test_justice_auth_feature_flag_disabled_for_normal_user(self, users, client):
        user = users["normal_user"]

        client.force_login(user)
        response = client.get(self.url)

        assert response.status_code == 404

    @patch("controlpanel.frontend.views.auth.oauth")
    def test_success(self, oauth, client, users):
        oauth.azure.authorize_access_token.return_value = {
            "userinfo": {
                "email": "email@example.com",
                "oid": "12345678"
            },
        }
        user = users["normal_user"]
        assert user.justice_email is None

        client.force_login(user)
        response = client.get(self.url, follow=True)

        user.refresh_from_db()
        assert user.justice_email == "email@example.com"
        assert user.azure_oid == "12345678"
        assertContains(response, "Successfully authenticated with your email email@example.com")

    @patch("controlpanel.frontend.views.auth.oauth")
    def test_failure(self, oauth, client, users):
        oauth.azure.authorize_access_token.side_effect = OAuthError()
        user = users["normal_user"]
        assert user.justice_email is None

        client.force_login(user)
        response = client.get(self.url, follow=True)

        user.refresh_from_db()
        assert user.justice_email is None
        assertContains(response, "Something went wrong, please try again")
