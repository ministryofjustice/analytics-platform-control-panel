# Standard library
import uuid
from unittest.mock import patch

# Third-party
from auth0.rest import Auth0Error
from bs4 import BeautifulSoup
from model_mommy import mommy
import pytest
from rest_framework import status
from rest_framework.reverse import reverse

# First-party/Local
from controlpanel.api.models import App


@pytest.fixture
def app():
    app = mommy.make("api.App")
    dev_auth_settings = dict(
        client_id="dev_client_id",
        group_id=str(uuid.uuid4())
    )
    prod_auth_settings = dict(
        client_id="prod_client_id",
        group_id=str(uuid.uuid4())
    )
    env_app_settings = dict(
        dev_env=dev_auth_settings,
        prod_env=prod_auth_settings,
    )
    app.app_conf = {
        App.KEY_WORD_FOR_AUTH_SETTINGS: env_app_settings
    }
    app.save()
    return app


@pytest.fixture
def ExtendedAuth0():
    with patch("controlpanel.api.models.app.auth0.ExtendedAuth0") as authz:
        yield authz.return_value


@pytest.fixture
def fixture_users_200(ExtendedAuth0):
    with patch.object(ExtendedAuth0.users, "all") as request:
        request.side_effect = [
            {
                "total": 200,
                "users": [
                    {
                        "name": f"Test User {(i * 100) + j}",
                        "email": f"test{(i * 100) + j}@example.com",
                        "user_id": f"github|{(i * 100) + j}",
                        "extra_field": True,
                    }
                    for j in range(100)
                ],
            }
            for i in range(2)
        ]
        yield


@pytest.fixture
def fixture_group_mocked(ExtendedAuth0):
    with patch.object(ExtendedAuth0.groups, "get_group_id") as request:
        request.side_effect = "my_group_id"
        yield request


@pytest.fixture
def fixture_customers_mocked(ExtendedAuth0):
    with patch.object(ExtendedAuth0.groups, "get_group_members_paginated") as request:
        items = [
            {
                "total": 250,
                "users": [
                    {
                        "name": f"Test User {(i * 5) + j}",
                        "email": f"test{(i * 5) + j}@example.com",
                        "user_id": f"github|{(i * 5) + j}",
                    }
                    for j in range(25)
                ],
            }
            for i in range(10)
        ]

        items.append([])

        request.side_effect = items
        yield request


def test_get(client, app, ExtendedAuth0):
    ExtendedAuth0.groups.get_group_members.return_value = [
        {
            "email": "a.user@digital.justice.gov.uk",
            "user_id": "email|5955f7ee86da0c1d55foobar",
            "nickname": "a.user",
            "name": "a.user@digital.justice.gov.uk",
            "foo": "bar",
            "baz": "bat",
        }
    ]

    response = client.get(reverse("appcustomers-list", (app.res_id,)))

    assert response.status_code == status.HTTP_200_OK
    assert len(response.data) == 1

    expected_fields = {
        "email",
        "user_id",
        "nickname",
        "name",
    }
    assert set(response.data[0]) == expected_fields


def test_post(client, app, ExtendedAuth0):
    emails = ["test1@example.com", "test2@example.com"]
    data = {"email": ", ".join(emails)}
    env_name = "dev_env"
    response = client.post(
        reverse("appcustomers-list", (app.res_id,)) + f"?env_name={env_name}",
        data)
    assert response.status_code == status.HTTP_201_CREATED

    ExtendedAuth0.add_group_members_by_emails.assert_called_with(
        emails=emails,
        user_options={"connection": "email"},
        group_id=app.get_group_id(env_name)
    )


def remove_chars(item_to_replace=[]):
    def wrap(item: str) -> str:
        for fltr in item_to_replace:
            _from, to = fltr
            item = item.replace(_from, to)
        return item

    return wrap


def get_buttons(content: str) -> list:
    soup = BeautifulSoup(content, "html.parser")
    menu_holder = soup.find("div", {"class": "pagination-menu"})
    return menu_holder.findAll("a", {"class": "govuk-button"})


def test_get_paginated(client, app, ExtendedAuth0, fixture_customers_mocked):
    group_id = app.get_group_id("dev_env")
    url_dict = {"group_id": group_id}
    page_no = 1

    response = client.get(
        reverse("appcustomers-page", args=(app.id, page_no)), url_dict
    )
    fixture_customers_mocked.assert_called_with(
        str(group_id), page=page_no, per_page=25
    )

    assert response.status_code == 200
    assert len(response.context_data.get("customers")) == 25

    buttons = get_buttons(response.content)
    btn_texts = [btn.text for btn in buttons]
    callback = remove_chars([(" ", ""), ("\n", "")])
    btn_texts = list(map(callback, btn_texts))
    expected = [str(i) for i in range(1, 11)] + ["Next"]
    for expect in expected:
        assert expect in btn_texts

    response = client.get(
        reverse("appcustomers-page", args=(app.id, page_no + 1)), url_dict
    )
    assert response.status_code == 200
    assert len(response.context_data.get("customers")) == 25
    buttons = get_buttons(response.content)

    btn_texts = [btn.text for btn in buttons]
    btn_texts = list(map(callback, btn_texts))
    expected = ["Previous"] + [str(i) for i in range(2, 11)] + ["Next"]
    for expect in expected:
        assert expect in btn_texts


def test_available_auth0_clients_on_customers_page(
        client, app, users, ExtendedAuth0, fixture_customers_mocked):
    client.force_login(users["superuser"])
    response = client.get(reverse("appcustomers-page", args=(app.id, 1)))

    assert response.status_code == 200
    for group_id, env_name in app.get_auth0_group_list().items():
        assert env_name in str(response.content)
        assert group_id in str(response.content)


def test_no_exist_auth0_clients_on_customers_page(client, app, users, ExtendedAuth0):
    with patch.object(ExtendedAuth0.groups, "get_group_members_paginated") as \
            get_group_members_paginated:
        group_id = app.get_group_id("dev_env")
        url_dict = {"group_id": group_id}
        error_msg = "Testing auth0 client call"
        get_group_members_paginated.side_effect = Auth0Error(
            status_code=404,
            error_code=404,
            message=error_msg)

        client.force_login(users["superuser"])
        response = client.get(reverse("appcustomers-page", args=(app.id, 1)), url_dict)

        assert response.status_code == 200
        assert error_msg in str(response.content)


def test_no_auth0_customers_page(client, app, users, ExtendedAuth0):
    app.app_conf = None
    app.save()
    message = "No need to manage the customers of the app on Control pane"
    client.force_login(users["superuser"])
    response = client.get(reverse("appcustomers-page", args=(app.id, 1)))

    assert response.status_code == 200
    assert message in str(response.content)
