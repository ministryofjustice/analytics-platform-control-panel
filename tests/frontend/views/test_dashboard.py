# Standard library
from unittest.mock import patch

# Third-party
import pytest
from django.conf import settings
from django.contrib.auth.models import Permission
from django.contrib.messages import get_messages
from django.urls import reverse
from model_bakery import baker
from rest_framework import status

# First-party/Local
from controlpanel.api.exceptions import DeleteCustomerError
from controlpanel.api.models import QUICKSIGHT_EMBED_AUTHOR_PERMISSION
from controlpanel.api.models.dashboard import Dashboard, DashboardViewer
from controlpanel.utils import GovukNotifyEmailError

NUM_DASHBOARDS = 3


@pytest.fixture()
def ExtendedAuth0():
    with patch("controlpanel.api.auth0.ExtendedAuth0") as ExtendedAuth0:
        ExtendedAuth0.return_value.add_dashboard_member_by_email.return_value = None
        yield ExtendedAuth0.return_value


@pytest.fixture(autouse=True)
def enable_db_for_all_tests(db):
    pass


@pytest.fixture
def users(users):

    user = baker.make(
        "api.User",
        auth0_id="github|dashboard-admin",
        username="dashboard_admin",
        justice_email="dashboard.admin@justice.gov.uk",
        is_superuser=False,
    )
    user.user_permissions.add(Permission.objects.get(codename=QUICKSIGHT_EMBED_AUTHOR_PERMISSION))
    users["dashboard_admin"] = user
    return users


@pytest.fixture
def dashboard(users, ExtendedAuth0):
    baker.make("api.Dashboard", NUM_DASHBOARDS - 1)
    dashboard = baker.make(
        "api.Dashboard",
        name="test-dashboard",
        quicksight_id="abc-123",
        created_by=users["dashboard_admin"],
    )

    dashboard.admins.add(users["dashboard_admin"])
    return dashboard


@pytest.fixture
def dashboard_viewer(users, dashboard):
    viewer = baker.make(DashboardViewer, email=users["dashboard_admin"].justice_email)
    dashboard.viewers.add(viewer)
    return viewer


@pytest.fixture
def dashboard_domain():
    domain = baker.make("api.DashboardDomain", name="justice.gov.uk")
    return domain


@pytest.fixture
def add_dashboard_domain(dashboard):
    domain = baker.make("api.DashboardDomain", name="test.gov.uk")
    dashboard.whitelist_domains.add(domain)
    return domain


def list_dashboards(client, *args):
    return client.get(reverse("list-dashboards"))


def list_all(client, *args):
    return client.get(reverse("list-all-dashboards"))


def detail(client, dashboard, *args):
    with patch("controlpanel.api.aws.AWSQuicksight.get_dashboard_embed_url") as mock_embed:
        mock_embed.return_value = "https://quicksight.aws.amazon.com/embed/test"
        return client.get(reverse("manage-dashboard-sharing", kwargs={"pk": dashboard.id}))


def create(client, *args):
    with patch("controlpanel.api.aws.AWSQuicksight.get_dashboards_for_user") as get_dashboards:
        get_dashboards.return_value = []
        return client.get(reverse("register-dashboard"))


def delete_get(client, dashboard, *args):
    return client.get(reverse("delete-dashboard", kwargs={"pk": dashboard.id}))


def delete_post(client, dashboard, *args):
    return client.post(reverse("delete-dashboard", kwargs={"pk": dashboard.id}))


def add_admin(client, dashboard, users, *args):
    data = {
        "user_id": users["other_user"].auth0_id,
    }
    return client.post(reverse("add-dashboard-admin", kwargs={"pk": dashboard.id}), data)


def revoke_admin(client, dashboard, users, *args):
    kwargs = {
        "pk": dashboard.id,
        "user_id": users["dashboard_admin"].auth0_id,
    }
    return client.post(reverse("revoke-dashboard-admin", kwargs=kwargs))


def add_customers(client, dashboard, *args):
    data = {
        "customer_email": "test@example.com",
    }
    return client.post(reverse("add-dashboard-customers", kwargs={"pk": dashboard.id}), data)


def remove_customers(client, dashboard, *args):
    data = {
        "customer": "1",
    }
    return client.post(reverse("remove-dashboard-customer", kwargs={"pk": dashboard.id}), data)


def remove_customer_by_email(client, dashboard, *args):
    return client.post(
        reverse("remove-dashboard-customer-by-email", kwargs={"pk": dashboard.id}), data={}
    )


def grant_domain_access_get(client, dashboard, users, dashboard_domain, *args):
    return client.get(reverse("grant-domain-access", kwargs={"pk": dashboard.id}))


def grant_domain_access_post(client, dashboard, users, dashboard_domain, *args):
    data = {
        "whitelist_domain": dashboard_domain.id,
    }
    return client.post(reverse("grant-domain-access", kwargs={"pk": dashboard.id}), data=data)


def revoke_domain_access_get(client, dashboard, users, dashboard_domain, *args):
    dashboard.whitelist_domains.add(dashboard_domain)
    return client.get(
        reverse(
            "revoke-domain-access", kwargs={"pk": dashboard.id, "domain_id": dashboard_domain.id}
        )
    )


def revoke_domain_access_post(client, dashboard, users, dashboard_domain, *args):
    dashboard.whitelist_domains.add(dashboard_domain)
    return client.post(
        reverse(
            "revoke-domain-access", kwargs={"pk": dashboard.id, "domain_id": dashboard_domain.id}
        ),
        data={},
    )


@pytest.mark.parametrize(
    "view,user,expected_status",
    [
        (list_dashboards, "superuser", status.HTTP_200_OK),
        (list_dashboards, "dashboard_admin", status.HTTP_200_OK),
        (list_dashboards, "normal_user", status.HTTP_403_FORBIDDEN),
        (list_all, "superuser", status.HTTP_200_OK),
        (list_all, "dashboard_admin", status.HTTP_403_FORBIDDEN),
        (list_all, "normal_user", status.HTTP_403_FORBIDDEN),
        (detail, "superuser", status.HTTP_200_OK),
        (detail, "dashboard_admin", status.HTTP_200_OK),
        (detail, "normal_user", status.HTTP_403_FORBIDDEN),
        (create, "superuser", status.HTTP_200_OK),
        (create, "dashboard_admin", status.HTTP_200_OK),
        (create, "normal_user", status.HTTP_403_FORBIDDEN),
        (delete_get, "superuser", status.HTTP_200_OK),
        (delete_get, "dashboard_admin", status.HTTP_200_OK),
        (delete_get, "normal_user", status.HTTP_403_FORBIDDEN),
        (delete_post, "superuser", status.HTTP_302_FOUND),
        (delete_post, "dashboard_admin", status.HTTP_302_FOUND),
        (delete_post, "normal_user", status.HTTP_403_FORBIDDEN),
        (add_admin, "superuser", status.HTTP_302_FOUND),
        (add_admin, "dashboard_admin", status.HTTP_302_FOUND),
        (add_admin, "normal_user", status.HTTP_403_FORBIDDEN),
        (revoke_admin, "superuser", status.HTTP_302_FOUND),
        (revoke_admin, "dashboard_admin", status.HTTP_302_FOUND),
        (revoke_admin, "normal_user", status.HTTP_403_FORBIDDEN),
        (add_customers, "superuser", status.HTTP_302_FOUND),
        (add_customers, "dashboard_admin", status.HTTP_302_FOUND),
        (add_customers, "normal_user", status.HTTP_403_FORBIDDEN),
        (remove_customers, "superuser", status.HTTP_302_FOUND),
        (remove_customers, "dashboard_admin", status.HTTP_302_FOUND),
        (remove_customers, "normal_user", status.HTTP_403_FORBIDDEN),
        (remove_customer_by_email, "superuser", status.HTTP_302_FOUND),
        (remove_customer_by_email, "dashboard_admin", status.HTTP_302_FOUND),
        (remove_customer_by_email, "normal_user", status.HTTP_403_FORBIDDEN),
        (grant_domain_access_get, "superuser", status.HTTP_200_OK),
        (grant_domain_access_get, "dashboard_admin", status.HTTP_200_OK),
        (grant_domain_access_get, "normal_user", status.HTTP_403_FORBIDDEN),
        (grant_domain_access_post, "superuser", status.HTTP_302_FOUND),
        (grant_domain_access_post, "dashboard_admin", status.HTTP_302_FOUND),
        (grant_domain_access_post, "normal_user", status.HTTP_403_FORBIDDEN),
        (revoke_domain_access_get, "superuser", status.HTTP_200_OK),
        (revoke_domain_access_get, "dashboard_admin", status.HTTP_200_OK),
        (revoke_domain_access_get, "normal_user", status.HTTP_403_FORBIDDEN),
        (revoke_domain_access_post, "superuser", status.HTTP_302_FOUND),
        (revoke_domain_access_post, "dashboard_admin", status.HTTP_302_FOUND),
        (revoke_domain_access_post, "normal_user", status.HTTP_403_FORBIDDEN),
    ],
)
def test_permissions(
    client, dashboard, users, dashboard_domain, view, user, expected_status, govuk_notify_send_email
):
    client.force_login(users[user])
    response = view(client, dashboard, users, dashboard_domain)
    assert response.status_code == expected_status


@pytest.mark.parametrize(
    "view,user,expected_count",
    [
        (list_dashboards, "superuser", 0),
        (list_dashboards, "dashboard_admin", 1),
        (list_all, "superuser", NUM_DASHBOARDS),
    ],
)
def test_list(client, dashboard, users, view, user, expected_count):
    client.force_login(users[user])
    response = view(client, dashboard, users)
    assert len(response.context_data["object_list"]) == expected_count


def test_list_dashboards_displays_success_message(client, users):
    """Dashboard list displays success message from session and clears it."""
    client.force_login(users["superuser"])
    session = client.session
    session["dashboard_created"] = {
        "name": "My New Dashboard",
        "url": "/quicksight/dashboards/123/",
    }
    session.save()

    response = client.get(reverse("list-dashboards"))

    assert response.status_code == 200
    assert response.context_data["dashboard_created"] == {
        "name": "My New Dashboard",
        "url": "/quicksight/dashboards/123/",
    }
    # Session should be cleared after displaying
    assert "dashboard_created" not in client.session


def test_list_dashboards_no_success_message(client, users):
    """Dashboard list returns None for dashboard_created when not in session."""
    client.force_login(users["superuser"])

    response = client.get(reverse("list-dashboards"))

    assert response.status_code == 200
    assert response.context_data["dashboard_created"] is None


def add_customer_success(client, response):
    return "customer_form_errors" not in client.session


def add_customer_form_error(client, response):
    return "customer_form_errors" in client.session


@pytest.mark.parametrize(
    "emails, expected_response, count",
    [
        ("foo@example.com", add_customer_success, 1),
        ("FOO@example.com", add_customer_success, 1),
        ("foo@example.com, bar@example.com", add_customer_success, 2),
        ("FOO@EXAMPLE.COM, Bar@example.com", add_customer_success, 2),
        ("foobar", add_customer_form_error, 0),
        ("foo@example.com, foobar", add_customer_form_error, 0),
        ("", add_customer_form_error, 0),
    ],
    ids=[
        "single-valid-email",
        "single-valid-email-uppercase",
        "multiple-delimited-emails",
        "multiple-delimited-emails-uppercase",
        "invalid-email",
        "mixed-valid-invalid-emails",
        "no-emails",
    ],
)
def test_add_customers(
    client,
    dashboard,
    dashboard_viewer,
    users,
    emails,
    expected_response,
    count,
    govuk_notify_send_email,
):
    client.force_login(users["superuser"])
    data = {"customer_email": emails}
    response = client.post(
        reverse("add-dashboard-customers", kwargs={"pk": dashboard.id}),
        data,
    )
    assert expected_response(client, response)
    emails = [email.strip().lower() for email in emails.split(",")]
    assert dashboard.viewers.filter(email__in=emails).count() == count


def test_add_customers_fail_notify(
    client,
    dashboard,
    dashboard_viewer,
    users,
):
    client.force_login(users["superuser"])
    data = {"customer_email": ["test.user@justice.gov.uk"]}
    with patch(
        "controlpanel.api.models.dashboard.govuk_notify_send_email"
    ) as govuk_notify_send_email:
        govuk_notify_send_email.side_effect = GovukNotifyEmailError()
        response = client.post(
            reverse("add-dashboard-customers", kwargs={"pk": dashboard.id}),
            data,
        )
        messages = [str(m) for m in get_messages(response.wsgi_request)]
        assert (
            "Failed to notify test.user@justice.gov.uk. "
            "You may wish to email them your dashboard link."
        ) in messages


def remove_customer_success(client, response):
    messages = [str(m) for m in get_messages(response.wsgi_request)]
    for message in messages:
        if "Successfully removed user" in message:
            return True

    return False


def remove_customer_failure(client, response):
    messages = [str(m) for m in get_messages(response.wsgi_request)]
    for message in messages:
        if "Failed removing user" in message:
            return True

    return False
    return "" in messages


@pytest.mark.parametrize(
    "side_effect, expected_response",
    [
        (None, remove_customer_success),
        (DeleteCustomerError, remove_customer_failure),
    ],
    ids=[
        "success",
        "failure",
    ],
)
def test_delete_customers(
    client,
    dashboard,
    users,
    dashboard_viewer,
    side_effect,
    expected_response,
):
    with patch(
        "controlpanel.frontend.views.dashboard.Dashboard.delete_customers_by_id"
    ) as delete_by_email:
        delete_by_email.side_effect = side_effect
        client.force_login(users["superuser"])
        data = {"customer": [dashboard_viewer.id]}

        response = client.post(
            reverse("remove-dashboard-customer", kwargs={"pk": dashboard.id}), data
        )
        assert expected_response(client, response)


def test_delete_cutomer_by_email_invalid_email(client, dashboard, users):
    client.force_login(users["superuser"])
    url = reverse("remove-dashboard-customer-by-email", kwargs={"pk": dashboard.id})
    response = client.post(
        url,
        data={
            "remove-email": "notanemail",
        },
    )
    messages = [str(m) for m in get_messages(response.wsgi_request)]
    assert response.status_code == 302
    assert "Invalid email address entered" in messages


@pytest.mark.parametrize(
    "side_effect, expected_message",
    [
        (None, "Successfully removed user email@example.com"),
        # fallback to display generic message if raised without one
        (DeleteCustomerError(), "Couldn't remove user with email email@example.com"),
        # specific error message displayed
        (DeleteCustomerError("API error"), "API error"),
    ],
)
def test_delete_customer_by_email(client, dashboard, users, side_effect, expected_message):
    client.force_login(users["superuser"])
    url = reverse("remove-dashboard-customer-by-email", kwargs={"pk": dashboard.id})
    with patch(
        "controlpanel.frontend.views.dashboard.Dashboard.delete_customer_by_email"
    ) as delete_by_email:
        delete_by_email.side_effect = side_effect
        response = client.post(
            url,
            data={"remove-email": "email@example.com"},
        )
        delete_by_email.assert_called_once()
        messages = [str(m) for m in get_messages(response.wsgi_request)]
        assert response.status_code == 302
        assert expected_message in messages


def test_add_dashboard_domain(client, dashboard, users, dashboard_domain):
    client.force_login(users["superuser"])
    url = reverse("grant-domain-access", kwargs={"pk": dashboard.id})

    response = client.post(
        url,
        data={"whitelist_domain": dashboard_domain.id},
    )

    assert response.status_code == 302
    updated_dashboard = Dashboard.objects.get(pk=dashboard.id)
    assert updated_dashboard.whitelist_domains.count() == 1


def test_revoke_dashboard_domain(client, dashboard, users, add_dashboard_domain):
    client.force_login(users["superuser"])
    url = reverse(
        "revoke-domain-access", kwargs={"pk": dashboard.id, "domain_id": add_dashboard_domain.id}
    )

    response = client.post(
        url,
        data={},
    )

    assert response.status_code == 302
    updated_dashboard = Dashboard.objects.get(pk=dashboard.id)
    assert updated_dashboard.whitelist_domains.count() == 0


@patch("controlpanel.api.aws.AWSQuicksight.get_dashboards_for_user")
def test_register_dashboard_rejects_id_not_in_user_list(get_dashboards, client, users):
    """
    Security test: Verify that a user cannot register a dashboard by submitting
    an arbitrary quicksight_id that is not in their list of owned dashboards.
    This prevents users from manipulating form data to register dashboards they don't own.
    """
    # User only owns "owned-dashboard-123"
    get_dashboards.return_value = [{"DashboardId": "owned-dashboard-123", "Name": "My Dashboard"}]
    client.force_login(users["superuser"])
    url = reverse("register-dashboard")

    # Attacker tries to submit a different dashboard ID
    response = client.post(
        url,
        data={
            "quicksight_id": "not-owned-dashboard-456",
            "description": "Trying to hijack",
            "emails[0]": "attacker@example.com",
        },
    )

    # Should be rejected with validation error (not a redirect)
    assert response.status_code == 200
    assert "Please select a valid dashboard from the list" in str(response.content)
    # Dashboard should NOT be created
    assert not Dashboard.objects.filter(quicksight_id="not-owned-dashboard-456").exists()


@patch("controlpanel.api.aws.AWSQuicksight.get_dashboards_for_user")
@patch("controlpanel.api.aws.AWSQuicksight.has_update_dashboard_permissions")
def test_register_dashboard_not_permitted(has_update_permissions, get_dashboards, client, users):
    has_update_permissions.return_value = False
    get_dashboards.return_value = [{"DashboardId": "abc-123", "Name": "Test Dashboard"}]
    client.force_login(users["superuser"])
    url = reverse("register-dashboard")
    response = client.post(
        url,
        data={
            "quicksight_id": "abc-123",
        },
    )
    has_update_permissions.assert_called_once_with(dashboard_id="abc-123", user=users["superuser"])
    assert response.status_code == 200
    assert "You do not have permission to register this dashboard" in str(response.content)


@patch("controlpanel.api.aws.AWSQuicksight.get_dashboards_for_user")
@patch("controlpanel.api.aws.AWSQuicksight.has_update_dashboard_permissions")
def test_register_dashboard_already_registered(
    has_update_permissions, get_dashboards, client, users, dashboard
):
    has_update_permissions.return_value = True
    get_dashboards.return_value = [
        {"DashboardId": dashboard.quicksight_id, "Name": "Test Dashboard"}
    ]
    client.force_login(users["superuser"])
    url = reverse("register-dashboard")
    response = client.post(
        url,
        data={
            "quicksight_id": dashboard.quicksight_id,
        },
    )
    has_update_permissions.assert_called_once_with(
        dashboard_id=dashboard.quicksight_id, user=users["superuser"]
    )
    assert response.status_code == 200
    assert (
        f"This dashboard has already been shared. Contact {dashboard.created_by.justice_email} to request sharing access."  # noqa
        in str(response.content)
    )


@patch("controlpanel.api.aws.AWSQuicksight.get_dashboards_for_user")
@patch("controlpanel.api.aws.AWSQuicksight.has_update_dashboard_permissions")
def test_register_dashboard_redirects_to_preview(
    has_update_permissions, get_dashboards, client, users
):
    """Valid form submission redirects to preview page and stores data in session."""
    has_update_permissions.return_value = True
    get_dashboards.return_value = [{"DashboardId": "abc-123", "Name": "Test Dashboard"}]
    client.force_login(users["superuser"])
    url = reverse("register-dashboard")
    response = client.post(
        url,
        data={
            "quicksight_id": "abc-123",
            "description": "Test description",
            "emails[0]": "viewer@example.com",
        },
    )
    assert response.status_code == 302
    assert response.url == reverse("preview-dashboard")
    # Check session data
    assert client.session["dashboard_preview"]["name"] == "Test Dashboard"
    assert client.session["dashboard_preview"]["quicksight_id"] == "abc-123"
    assert client.session["dashboard_preview"]["description"] == "Test description"
    assert client.session["dashboard_preview"]["emails"] == ["viewer@example.com"]
    # Dashboard should not be created yet
    assert not Dashboard.objects.filter(quicksight_id="abc-123").exists()


@patch("controlpanel.api.aws.AWSQuicksight.get_dashboards_for_user")
@patch("controlpanel.api.aws.AWSQuicksight.has_update_dashboard_permissions")
def test_register_dashboard_with_valid_emails(
    has_update_permissions, get_dashboards, client, users
):
    """Registration with valid emails stores them in session for preview."""
    has_update_permissions.return_value = True
    get_dashboards.return_value = [{"DashboardId": "def-456", "Name": "Test Dashboard"}]
    client.force_login(users["superuser"])
    url = reverse("register-dashboard")
    response = client.post(
        url,
        data={
            "quicksight_id": "def-456",
            "description": "Test description",
            "emails[0]": "viewer1@example.com",
            "emails[1]": "viewer2@example.com",
        },
    )
    assert response.status_code == 302
    assert response.url == reverse("preview-dashboard")
    assert client.session["dashboard_preview"]["emails"] == [
        "viewer1@example.com",
        "viewer2@example.com",
    ]


@patch("controlpanel.api.aws.AWSQuicksight.get_dashboards_for_user")
@patch("controlpanel.api.aws.AWSQuicksight.has_update_dashboard_permissions")
def test_register_dashboard_with_invalid_emails(
    has_update_permissions, get_dashboards, client, users, ExtendedAuth0
):
    """Registration with invalid emails shows validation errors."""
    has_update_permissions.return_value = True
    get_dashboards.return_value = [{"DashboardId": "ghi-789", "Name": "Test Dashboard"}]
    client.force_login(users["superuser"])
    url = reverse("register-dashboard")
    response = client.post(
        url,
        data={
            "quicksight_id": "ghi-789",
            "description": "Test description",
            "emails[0]": "not-an-email",
            "emails[1]": "also-invalid",
        },
    )
    assert response.status_code == 200
    # Check form has email validation errors
    assert "Enter a valid email address" in str(response.content)
    # Dashboard should not be created
    assert not Dashboard.objects.filter(quicksight_id="ghi-789").exists()


@patch("controlpanel.api.aws.AWSQuicksight.get_dashboards_for_user")
@patch("controlpanel.api.aws.AWSQuicksight.has_update_dashboard_permissions")
def test_register_dashboard_with_empty_emails(
    has_update_permissions, get_dashboards, client, users, dashboard_domain
):
    """Registration with no emails but with whitelist_domain redirects to preview."""
    has_update_permissions.return_value = True
    get_dashboards.return_value = [{"DashboardId": "jkl-012", "Name": "Test Dashboard"}]
    client.force_login(users["superuser"])
    url = reverse("register-dashboard")
    response = client.post(
        url,
        data={
            "quicksight_id": "jkl-012",
            "description": "Test description",
            "whitelist_domain": dashboard_domain.id,
        },
    )
    assert response.status_code == 302
    assert response.url == reverse("preview-dashboard")
    assert client.session["dashboard_preview"]["emails"] == []


@patch("controlpanel.api.aws.AWSQuicksight.get_dashboards_for_user")
@patch("controlpanel.api.aws.AWSQuicksight.has_update_dashboard_permissions")
def test_register_dashboard_requires_email_or_domain(
    has_update_permissions, get_dashboards, client, users
):
    """Registration without emails AND without whitelist_domain shows validation error."""
    has_update_permissions.return_value = True
    get_dashboards.return_value = [{"DashboardId": "xyz-123", "Name": "Test Dashboard"}]
    client.force_login(users["superuser"])
    url = reverse("register-dashboard")
    response = client.post(
        url,
        data={
            "quicksight_id": "xyz-123",
            "description": "Test description",
            # No emails and no whitelist_domain
        },
    )
    assert response.status_code == 200
    # Check for validation error requiring at least one
    assert "Enter an email address or add domain access" in str(response.content)
    # Dashboard should not be created
    assert not Dashboard.objects.filter(quicksight_id="xyz-123").exists()


def test_preview_dashboard_without_session_redirects(client, users):
    """Accessing preview page without session data redirects to register."""
    client.force_login(users["superuser"])
    url = reverse("preview-dashboard")
    response = client.get(url)
    assert response.status_code == 302
    assert response.url == reverse("register-dashboard")


def test_preview_dashboard_rejects_other_users_session_data(client, users):
    """Preview page rejects session data belonging to a different user."""
    client.force_login(users["superuser"])
    session = client.session
    # Session data with a different user's ID
    session["dashboard_preview"] = {
        "user_id": users["normal_user"].id,  # Different user
        "name": "Other User Dashboard",
        "description": "Should not be accessible",
        "quicksight_id": "other-123",
        "emails": [],
    }
    session.save()

    url = reverse("preview-dashboard")
    response = client.get(url)

    # Should redirect to register and clear the stale session data
    assert response.status_code == 302
    assert response.url == reverse("register-dashboard")
    assert "dashboard_preview" not in client.session


@patch("controlpanel.api.aws.AWSQuicksight.get_dashboards_for_user")
def test_register_dashboard_prepopulates_from_session(get_dashboards, client, users):
    """Registration form is pre-populated with session data when returning from preview."""
    get_dashboards.return_value = [{"DashboardId": "abc-123", "Name": "Test Dashboard"}]
    client.force_login(users["superuser"])

    # Set up session data as if returning from preview via "Change" link
    session = client.session
    session["dashboard_preview"] = {
        "user_id": users["superuser"].id,
        "name": "Test Dashboard",
        "description": "My description",
        "quicksight_id": "abc-123",
        "emails": ["viewer1@example.com", "viewer2@example.com"],
    }
    session.save()

    url = reverse("register-dashboard")
    response = client.get(url)

    assert response.status_code == 200
    # Check description is populated
    assert "My description" in str(response.content)
    # Check emails are populated
    assert "viewer1@example.com" in str(response.content)
    assert "viewer2@example.com" in str(response.content)
    # Check dashboard option is selected
    assert "selected" in str(response.content)


@patch("controlpanel.api.aws.AWSQuicksight.get_dashboard_embed_url")
def test_preview_dashboard_displays_session_data(mock_embed_url, client, users):
    """Preview page displays data from session and embeds dashboard."""
    mock_embed_url.return_value = "https://quicksight.aws.amazon.com/embed/test-url"
    client.force_login(users["superuser"])
    session = client.session
    session["dashboard_preview"] = {
        "user_id": users["superuser"].id,
        "name": "My Dashboard",
        "description": "A test dashboard",
        "quicksight_id": "preview-123",
        "emails": ["user1@example.com", "user2@example.com"],
    }
    session.save()

    url = reverse("preview-dashboard")
    response = client.get(url)
    assert response.status_code == 200
    assert "My Dashboard" in str(response.content)
    assert "A test dashboard" in str(response.content)
    assert "user1@example.com" in str(response.content)
    assert "user2@example.com" in str(response.content)
    # Check embed URL is included
    assert "https://quicksight.aws.amazon.com/embed/test-url" in str(response.content)
    assert "dashboard-container" in str(response.content)
    mock_embed_url.assert_called_once_with(user=users["superuser"], dashboard_id="preview-123")


@patch("controlpanel.api.aws.AWSQuicksight.get_dashboard_embed_url")
def test_preview_dashboard_without_embed_url(mock_embed_url, client, users):
    """Preview page shows fallback message when embed URL is not available."""
    mock_embed_url.return_value = None
    client.force_login(users["superuser"])
    session = client.session
    session["dashboard_preview"] = {
        "user_id": users["superuser"].id,
        "name": "My Dashboard",
        "description": "A test dashboard",
        "quicksight_id": "preview-123",
        "emails": [],
    }
    session.save()

    url = reverse("preview-dashboard")
    response = client.get(url)
    assert response.status_code == 200
    assert "Dashboard preview is not available" in str(response.content)
    assert "dashboard-container" not in str(response.content)


def test_preview_dashboard_confirm_creates_dashboard(
    client, users, ExtendedAuth0, govuk_notify_send_email
):
    """Confirming preview creates dashboard with viewers."""
    client.force_login(users["superuser"])
    session = client.session
    session["dashboard_preview"] = {
        "user_id": users["superuser"].id,
        "name": "Confirmed Dashboard",
        "description": "Confirmed description",
        "quicksight_id": "confirm-123",
        "emails": ["viewer@example.com"],
    }
    session.save()

    url = reverse("preview-dashboard")
    response = client.post(url)

    dashboard = Dashboard.objects.get(quicksight_id="confirm-123")
    assert response.status_code == 302
    assert response.url == reverse("list-dashboards")
    assert dashboard.name == "Confirmed Dashboard"
    assert dashboard.description == "Confirmed description"
    assert dashboard.created_by == users["superuser"]
    assert users["superuser"] in dashboard.admins.all()
    # Check viewers (creator + additional email)
    viewer_emails = list(dashboard.viewers.values_list("email", flat=True))
    assert users["superuser"].justice_email.lower() in viewer_emails
    assert "viewer@example.com" in viewer_emails
    # Session should be cleared
    assert "dashboard_preview" not in client.session

    govuk_notify_send_email.assert_called_once_with(
        email_address="viewer@example.com",
        template_id=settings.NOTIFY_DASHBOARD_ACCESS_TEMPLATE_ID,
        personalisation={
            "dashboard": dashboard.name,
            "dashboard_link": dashboard.url,
            "dashboard_home": settings.DASHBOARD_SERVICE_URL,
            "dashboard_admin": users["superuser"].justice_email.lower(),
            "dashboard_description": dashboard.description,
        },
    )


def test_preview_dashboard_confirm_creates_dashboard_with_whitelist_domain(
    client, users, dashboard_domain, ExtendedAuth0
):
    """Confirming preview creates dashboard with whitelist domain."""
    client.force_login(users["superuser"])
    session = client.session
    session["dashboard_preview"] = {
        "user_id": users["superuser"].id,
        "name": "Dashboard With Domain",
        "description": "Description",
        "quicksight_id": "domain-123",
        "emails": [],
        "whitelist_domain": dashboard_domain.name,
    }
    session.save()

    url = reverse("preview-dashboard")
    response = client.post(url)

    dashboard = Dashboard.objects.get(quicksight_id="domain-123")
    assert response.status_code == 302
    assert dashboard.whitelist_domains.count() == 1
    assert dashboard_domain in dashboard.whitelist_domains.all()


@patch("controlpanel.api.aws.AWSQuicksight.get_dashboards_for_user")
@patch("controlpanel.api.aws.AWSQuicksight.has_update_dashboard_permissions")
def test_register_dashboard_with_whitelist_domain(
    has_update_permissions, get_dashboards, client, users, dashboard_domain
):
    """Registration with whitelist domain stores it in session for preview."""
    has_update_permissions.return_value = True
    get_dashboards.return_value = [{"DashboardId": "domain-456", "Name": "Test Dashboard"}]
    client.force_login(users["superuser"])
    url = reverse("register-dashboard")
    response = client.post(
        url,
        data={
            "quicksight_id": "domain-456",
            "description": "Test description",
            "whitelist_domain": dashboard_domain.id,
        },
    )
    assert response.status_code == 302
    assert response.url == reverse("preview-dashboard")
    assert client.session["dashboard_preview"]["whitelist_domain"] == dashboard_domain.name


def test_cancel_dashboard_registration_clears_session(client, users):
    """Cancel registration clears session data and redirects to list-dashboards."""
    client.force_login(users["superuser"])
    session = client.session
    session["dashboard_preview"] = {
        "user_id": users["superuser"].id,
        "name": "Test Dashboard",
        "quicksight_id": "test-123",
    }
    session.save()

    url = reverse("cancel-dashboard-registration")
    response = client.get(url)

    assert response.status_code == 302
    assert response.url == reverse("list-dashboards")
    assert "dashboard_preview" not in client.session


@pytest.mark.parametrize(
    "user_id, expected_message, count",
    [
        ("invalid_user", "User not found", 0),
        ("", "User not found", 0),
        ("github|user_3", "User cannot be added as a dashboard admin", 0),
        ("github|user_5", "Granted admin access to ", 1),
    ],
)
def test_add_admin(
    user_id, expected_message, count, client, dashboard, users, govuk_notify_send_email
):
    client.force_login(users["superuser"])
    url = reverse("add-dashboard-admin", kwargs={"pk": dashboard.id})
    data = {
        "user_id": user_id,
    }
    response = client.post(url, data)
    assert response.status_code == 302
    assert response.url == reverse("manage-dashboard-sharing", kwargs={"pk": dashboard.id})
    assert dashboard.admins.filter(auth0_id=user_id).count() == count
    messages = [str(m) for m in get_messages(response.wsgi_request)]
    assert expected_message in messages
    if count:
        govuk_notify_send_email.assert_called_once()


def test_preview_dashboard_confirm_creates_dashboard_fail_notify(client, users, ExtendedAuth0):
    """Confirming preview creates dashboard but shows error if notify fails."""
    client.force_login(users["superuser"])
    session = client.session
    session["dashboard_preview"] = {
        "user_id": users["superuser"].id,
        "name": "Confirmed Dashboard",
        "description": "Confirmed description",
        "quicksight_id": "confirm-123",
        "emails": ["viewer@example.com"],
    }
    session.save()

    url = reverse("preview-dashboard")

    with patch("controlpanel.api.models.dashboard.govuk_notify_send_email") as mock_send_email:
        mock_send_email.side_effect = GovukNotifyEmailError()
        response = client.post(url)

    # Dashboard should still be created
    dashboard = Dashboard.objects.get(quicksight_id="confirm-123")
    assert response.status_code == 302
    assert response.url == reverse("list-dashboards")
    assert dashboard.name == "Confirmed Dashboard"

    # Check viewers (viewer should still be added despite email failure)
    viewer_emails = list(dashboard.viewers.values_list("email", flat=True))
    assert "viewer@example.com" in viewer_emails

    # Check error message
    messages = [str(m) for m in get_messages(response.wsgi_request)]
    assert (
        "Failed to notify viewer@example.com. " "You may wish to email them your dashboard link."
    ) in messages
