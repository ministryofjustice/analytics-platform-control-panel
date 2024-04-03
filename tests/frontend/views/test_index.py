# Third-party
import pytest
from django.http import HttpResponse
from django.urls import reverse
from mock import MagicMock, patch


class TestAccess:

    @pytest.mark.parametrize("method, status_code", [
        ("get", 302),
        ("post", 302),

    ])
    def test_not_logged_in_redirects(self, method, status_code, client):
        response = getattr(client, method)("/")
        assert response.status_code == status_code

    @patch("django.conf.settings.features.justice_auth.enabled", False)
    @pytest.mark.parametrize("method, status_code", [
        ("get", 302),
        ("post", 405),
    ])
    def test_justice_auth_feature_flag_disabled_for_normal_user(
        self, method, status_code, client, users,
    ):
        client.force_login(users["normal_user"])
        response = getattr(client, method)("/")
        assert response.status_code == status_code


class TestGetAsSuperuser:

    def test_without_justice_email(self, client, superuser):
        client.force_login(superuser)
        assert superuser.justice_email is None

        response = client.get("/")

        assert response.status_code == 200
        assert response.template_name == ["justice_email.html"]

    def test_with_justice_email(self, client, superuser):
        superuser.justice_email = "email@example.com"
        superuser.save()
        client.force_login(superuser)

        response = client.get("/")

        assert response.status_code == 200
        assert response.template_name == ["home.html"]


class TestGetAsNormalUser:
    def test_without_justice_email(self, client, users):
        user = users["normal_user"]
        client.force_login(user)
        assert user.justice_email is None

        response = client.get("/")

        assert response.status_code == 200
        assert response.template_name == ["justice_email.html"]

    def test_with_justice_email(self, client, users):
        user = users["normal_user"]
        user.justice_email = "email@example.com"
        user.save()
        client.force_login(user)

        response = client.get("/")

        assert response.status_code == 302
        assert response.url == reverse("list-tools")


class TestPost:

    @patch("controlpanel.frontend.views.get_code_challenge", new=MagicMock(return_value="codeabc"))
    @pytest.mark.parametrize("user", [
        "superuser",
        "normal_user"
    ])
    def test_superuser_authorize_redirect_called(self, user, client, users):
        user = users[user]
        client.force_login(user)
        with patch("controlpanel.frontend.views.oauth") as oauth:
            oauth.azure.authorize_redirect.return_value = HttpResponse()

            response = client.post("/")

            oauth.azure.authorize_redirect.assert_called_once_with(
                response.wsgi_request,
                f"http://testserver{reverse('entraid-auth')}",
                code_challenge="codeabc",
            )
