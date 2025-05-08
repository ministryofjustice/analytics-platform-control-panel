# Standard library
from unittest.mock import patch

# Third-party
import pytest
from django.conf import settings
from django.contrib.messages import get_messages
from django.urls import reverse
from model_bakery import baker
from rest_framework import status

# First-party/Local
from controlpanel.api.exceptions import DeleteCustomerError
from controlpanel.api.models.dashboard import Dashboard, DashboardViewer

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
    users.update(
        {
            "dashboard_admin": baker.make(
                "api.User",
                auth0_id="github|dashboard-admin",
                username="dashboard_admin",
                justice_email="dashboard.admin@justice.gov.uk",
            ),
        }
    )
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
    return client.get(reverse("manage-dashboard", kwargs={"pk": dashboard.id}))


def create(client, *args):
    return client.get(reverse("register-dashboard"))


def delete(client, dashboard, *args):
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
        "customer": "email|user_1",
    }
    return client.post(reverse("remove-dashboard-customer", kwargs={"pk": dashboard.id}), data)


def remove_customer_by_email(client, dashboard, *args):
    return client.post(
        reverse("remove-dashboard-customer-by-email", kwargs={"pk": dashboard.id}), data={}
    )


def grant_domain_access(client, dashboard, users, dashboard_domain, *args):
    data = {
        "whitelist_domain": dashboard_domain.id,
    }
    return client.post(reverse("grant-domain-access", kwargs={"pk": dashboard.id}), data=data)


def revoke_domain_access(client, dashboard, users, dashboard_domain, *args):
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
        (list_dashboards, "normal_user", status.HTTP_200_OK),
        (list_all, "superuser", status.HTTP_200_OK),
        (list_all, "dashboard_admin", status.HTTP_403_FORBIDDEN),
        (list_all, "normal_user", status.HTTP_403_FORBIDDEN),
        (detail, "superuser", status.HTTP_200_OK),
        (detail, "dashboard_admin", status.HTTP_200_OK),
        (detail, "normal_user", status.HTTP_403_FORBIDDEN),
        (create, "superuser", status.HTTP_200_OK),
        (create, "dashboard_admin", status.HTTP_200_OK),
        (create, "normal_user", status.HTTP_200_OK),
        (delete, "superuser", status.HTTP_302_FOUND),
        (delete, "dashboard_admin", status.HTTP_302_FOUND),
        (delete, "normal_user", status.HTTP_403_FORBIDDEN),
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
        (grant_domain_access, "superuser", status.HTTP_302_FOUND),
        (grant_domain_access, "dashboard_admin", status.HTTP_302_FOUND),
        (grant_domain_access, "normal_user", status.HTTP_403_FORBIDDEN),
        (revoke_domain_access, "superuser", status.HTTP_302_FOUND),
        (revoke_domain_access, "dashboard_admin", status.HTTP_302_FOUND),
        (revoke_domain_access, "normal_user", status.HTTP_403_FORBIDDEN),
    ],
)
def test_permissions(client, dashboard, users, dashboard_domain, view, user, expected_status):
    client.force_login(users[user])
    response = view(client, dashboard, users, dashboard_domain)
    assert response.status_code == expected_status


@pytest.mark.parametrize(
    "view,user,expected_count",
    [
        (list_dashboards, "superuser", 0),
        (list_dashboards, "normal_user", 0),
        (list_dashboards, "dashboard_admin", 1),
        (list_all, "superuser", NUM_DASHBOARDS),
    ],
)
def test_list(client, dashboard, users, view, user, expected_count):
    client.force_login(users[user])
    response = view(client, dashboard, users)
    assert len(response.context_data["object_list"]) == expected_count


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
def test_add_customers(client, dashboard, dashboard_viewer, users, emails, expected_response, count):
    client.force_login(users["superuser"])
    data = {"customer_email": emails}
    response = client.post(
        reverse("add-dashboard-customers", kwargs={"pk": dashboard.id}),
        data,
    )
    assert expected_response(client, response)
    emails = [email.strip().lower() for email in emails.split(",")]
    assert dashboard.viewers.filter(email__in=emails).count() == count


def remove_customer_success(client, response):
    messages = [str(m) for m in get_messages(response.wsgi_request)]
    return "Successfully removed customer" in messages


def remove_customer_failure(client, response):
    messages = [str(m) for m in get_messages(response.wsgi_request)]
    return "Failed removing customer" in messages


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
        (None, "Successfully removed customer email@example.com"),
        # fallback to display generic message if raised without one
        (DeleteCustomerError(), "Couldn't remove customer with email email@example.com"),
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


@pytest.mark.parametrize(
    "dashboard_url",
    [
        ("https://not-quicksight.com/sn/dashboards/abc-123"),
        ("https://eu-west-1.quicksight.com/sn/dashboards/abc-123"),
        (f"https://{settings.QUICKSIGHT_ACCOUNT_REGION}.aws.amazon.com/sn/dashboards/"),
    ],
)
def test_register_dashboard_invalid_url(dashboard_url, client, users):
    client.force_login(users["superuser"])
    url = reverse("register-dashboard")
    response = client.post(
        url,
        data={
            "name": "Test Dashboard",
            "quicksight_id": dashboard_url,
        },
    )

    assert response.status_code == 200
    assert "The URL entered is not a valid Quicksight dashboard URL" in str(response.content)


def test_register_dashboard_not_permitted(client, users):
    with patch(
        "controlpanel.api.aws.AWSQuicksight.has_update_dashboard_permissions"
    ) as has_update_permissions:
        has_update_permissions.return_value = False
        client.force_login(users["superuser"])
        url = reverse("register-dashboard")
        response = client.post(
            url,
            data={
                "name": "Test Dashboard",
                "quicksight_id": f"https://{settings.QUICKSIGHT_ACCOUNT_REGION}.quicksight.aws.amazon.com/sn/dashboards/abc-123",  # noqa
            },
        )
        has_update_permissions.assert_called_once_with(
            dashboard_id="abc-123", user=users["superuser"]
        )
        assert response.status_code == 200
        assert "You do not have permission to register this dashboard" in str(response.content)


def test_register_dashboard_already_registered(client, users, dashboard):
    with patch(
        "controlpanel.api.aws.AWSQuicksight.has_update_dashboard_permissions"
    ) as has_update_permissions:
        has_update_permissions.return_value = True
        client.force_login(users["superuser"])
        url = reverse("register-dashboard")
        response = client.post(
            url,
            data={
                "name": "Test Dashboard 2",
                "quicksight_id": f"https://{settings.QUICKSIGHT_ACCOUNT_REGION}.quicksight.aws.amazon.com/sn/dashboards/{dashboard.quicksight_id}",  # noqa
            },
        )
        has_update_permissions.assert_called_once_with(
            dashboard_id=dashboard.quicksight_id, user=users["superuser"]
        )
        assert response.status_code == 200
        assert (
            f"This dashboard is already registered by {dashboard.created_by.justice_email}. Please contact them to request access."  # noqa
            in str(response.content)
        )


def test_register_dashboard_success(client, users, ExtendedAuth0):
    with patch(
        "controlpanel.api.aws.AWSQuicksight.has_update_dashboard_permissions"
    ) as has_update_permissions:
        has_update_permissions.return_value = True
        client.force_login(users["superuser"])
        url = reverse("register-dashboard")
        response = client.post(
            url,
            data={
                "name": "Test Dashboard",
                "quicksight_id": f"https://{settings.QUICKSIGHT_ACCOUNT_REGION}.quicksight.aws.amazon.com/sn/dashboards/abc-123",  # noqa
            },
        )
        has_update_permissions.assert_called_once_with(
            dashboard_id="abc-123", user=users["superuser"]
        )
        dashboard = Dashboard.objects.get(name="Test Dashboard", quicksight_id="abc-123")
        assert response.status_code == 302
        assert response.url == reverse("manage-dashboard", kwargs={"pk": dashboard.pk})
        ExtendedAuth0.add_dashboard_member_by_email.assert_called_once_with(
            email=users["superuser"].justice_email.lower(),
            user_options={"connection": "email"},
        )
