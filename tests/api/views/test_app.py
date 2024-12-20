# Standard library
from unittest.mock import patch

# Third-party
import pytest
from botocore.exceptions import ClientError
from django.conf import settings
from model_bakery import baker
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.reverse import reverse

# First-party/Local
from controlpanel.api.models import App
from controlpanel.api.serializers import AppSerializer
from tests.api.fixtures.aws import *


@pytest.fixture  # noqa: F405
def app():
    return baker.make(
        "api.App",
        repo_url="https://github.com/ministryofjustice/example.git",
        app_conf={
            App.KEY_WORD_FOR_AUTH_SETTINGS: {
                "dev": {"group_id": "dev_group_id"},
                "prod": {"group_id": "prod_group_id"},
            }
        },
    )


@pytest.fixture(autouse=True)  # noqa: F405
def models(app, users):
    with (
        patch("controlpanel.api.aws.AWSRole.grant_bucket_access"),
        patch("controlpanel.api.aws.AWSBucket.create"),
    ):
        baker.make("api.App")
        baker.make("api.AppS3Bucket", app=app)
        baker.make("api.UserApp", app=app, user=users["superuser"])


def test_list(client):
    response = client.get(reverse("app-list"))
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data["results"]) == 2


def test_list_filter_by_repo_url(client, app):
    response = client.get(
        reverse("app-list"),
        {"repo_url": app.repo_url},
    )

    assert response.status_code == status.HTTP_200_OK
    results = response.data["results"]
    assert len(results) == 1
    assert results[0]["res_id"] == str(app.res_id)


def test_detail(client, app):
    response = client.get(reverse("app-detail", (app.res_id,)))
    assert response.status_code == status.HTTP_200_OK

    expected_fields = {
        "res_id",
        "url",
        "name",
        "description",
        "slug",
        "repo_url",
        "iam_role_name",
        "created_by",
        "apps3buckets",
        "userapps",
        "ip_allowlists",
        "app_allowed_ip_ranges",
    }
    assert expected_fields == set(response.data)
    assert response.data["iam_role_name"] == app.iam_role_name

    apps3bucket = response.data["apps3buckets"][0]
    expected_fields = {"id", "url", "s3bucket", "access_level"}
    assert set(apps3bucket) == expected_fields

    expected_fields = {
        "id",
        "url",
        "name",
        "arn",
        "created_by",
        "is_data_warehouse",
    }
    assert set(apps3bucket["s3bucket"]) == expected_fields

    userapp = response.data["userapps"][0]
    expected_fields = {"id", "user", "is_admin"}
    assert set(userapp) == expected_fields

    expected_fields = {
        "auth0_id",
        "url",
        "username",
        "name",
        "email",
    }
    assert set(userapp["user"]) == expected_fields


@pytest.fixture
def customer():
    return {
        "email": "a.user@digital.justice.gov.uk",
        "user_id": "email|5955f7ee86da0c1d55foobar",
        "nickname": "a.user",
        "name": "a.user@digital.justice.gov.uk",
        "foo": "bar",
        "baz": "bat",
    }


@pytest.mark.parametrize("env_name", ["dev", "prod"], ids=["dev", "prod"])
def test_app_by_name_get_customers(client, app, customer, env_name):
    with patch("controlpanel.api.models.App.customer_paginated") as customer_paginated:
        customer_paginated.return_value = {"total": 1, "users": [customer]}

        response = client.get(
            reverse("apps-by-name-customers", kwargs={"name": app.name}),
            query_params={"env_name": env_name},
        )
        assert response.status_code == status.HTTP_200_OK
        app.customer_paginated.assert_called_once()

        expected_fields = {
            "email",
            "user_id",
            "nickname",
            "name",
        }
        assert response.data["results"] == [{field: customer[field] for field in expected_fields}]


@pytest.mark.parametrize("env_name", ["", "foo"])
def test_app_by_name_get_customers_invalid(client, app, env_name):
    with patch("controlpanel.api.models.App.customer_paginated") as customer_paginated:

        response = client.get(
            reverse("apps-by-name-customers", kwargs={"name": app.name}),
            query_params={"env_name": env_name},
        )
        customer_paginated.assert_not_called()
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.parametrize("env_name", ["dev", "prod"])
def test_app_by_name_add_customers(client, app, env_name):
    emails = ["test1@example.com", "test2@example.com"]
    data = {"emails": ", ".join(emails), "env_name": env_name}

    with patch("controlpanel.api.models.App.add_customers") as add_customers:
        url = reverse("apps-by-name-customers", kwargs={"name": app.name})
        response = client.post(url, data=data)

        assert response.status_code == status.HTTP_201_CREATED
        add_customers.assert_called_once_with(emails, env_name=env_name)


@pytest.mark.parametrize("env_name", ["", "foo"])
def test_app_by_name_add_customers_invalid(client, app, env_name):
    emails = ["test1@example.com", "test2@example.com"]
    data = {"emails": ", ".join(emails)}

    with patch("controlpanel.api.models.App.add_customers") as add_customers:
        add_customers.side_effect = app.AddCustomerError
        url = reverse("apps-by-name-customers", kwargs={"name": app.name})
        response = client.post(url, data=data)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        add_customers.assert_not_called()


def test_app_detail_by_name(client, app):
    response = client.get(reverse("apps-by-name-detail", (app.name,)))
    assert response.status_code == status.HTTP_200_OK

    expected_fields = {
        "res_id",
        "url",
        "name",
        "description",
        "slug",
        "repo_url",
        "iam_role_name",
        "created_by",
        "apps3buckets",
        "userapps",
        "ip_allowlists",
        "app_allowed_ip_ranges",
    }
    assert expected_fields == set(response.data)
    assert response.data["iam_role_name"] == app.iam_role_name

    apps3bucket = response.data["apps3buckets"][0]
    expected_fields = {"id", "url", "s3bucket", "access_level"}
    assert set(apps3bucket) == expected_fields

    expected_fields = {
        "id",
        "url",
        "name",
        "arn",
        "created_by",
        "is_data_warehouse",
    }
    assert set(apps3bucket["s3bucket"]) == expected_fields

    userapp = response.data["userapps"][0]
    expected_fields = {"id", "user", "is_admin"}
    assert set(userapp) == expected_fields

    expected_fields = {
        "auth0_id",
        "url",
        "username",
        "name",
        "email",
    }
    assert set(userapp["user"]) == expected_fields


@pytest.fixture  # noqa: F405
def authz():
    with patch("controlpanel.api.auth0.ExtendedAuth0") as authz:
        yield authz()


def test_delete(client, app, authz):
    with patch("controlpanel.api.aws.AWSRole.delete_role") as delete_role:
        response = client.delete(reverse("app-detail", (app.res_id,)))
        assert response.status_code == status.HTTP_204_NO_CONTENT

        # authz.clear_up_app.assert_called_with(app_name=app.slug, group_name=app.slug)
        delete_role.assert_called_with(app.iam_role_name)

        response = client.get(reverse("app-detail", (app.res_id,)))
        assert response.status_code == status.HTTP_404_NOT_FOUND


def test_create(client, users, sqs, helpers):
    data = {"name": "bar", "repo_url": "https://github.com/ministryofjustice/new-example.git"}
    response = client.post(reverse("app-list"), data)
    assert response.status_code == status.HTTP_201_CREATED

    assert response.data["created_by"] == users["superuser"].auth0_id
    assert response.data["repo_url"] == "https://github.com/ministryofjustice/new-example"

    app = App.objects.get(repo_url="https://github.com/ministryofjustice/new-example")
    messages = helpers.retrieve_messages(sqs, queue_name=settings.IAM_QUEUE_NAME)
    helpers.validate_task_with_sqs_messages(
        messages, App.__name__, app.id, queue_name=settings.IAM_QUEUE_NAME
    )


def test_update(client, app):
    data = {"name": "foo", "repo_url": "https://github.com/ministryofjustice/new.git"}
    response = client.put(
        reverse("app-detail", (app.res_id,)),
        data,
        content_type="application/json",
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.data["name"] == data["name"]
    assert response.data["repo_url"] == "https://github.com/ministryofjustice/new"


@pytest.mark.skip(
    reason="The step of creating aws role has been moved " "out but keep test for future reference"
)
def test_aws_error_and_transaction(client):
    with patch("controlpanel.api.aws.AWSRole.create_role") as create_app_role:
        create_app_role.side_effect = ClientError({}, "CreateRole")
        data = {"name": "quux", "repo_url": "https://example.com/quux.git"}

        with pytest.raises(ClientError):  # noqa: F405
            client.post(reverse("app-list"), data)

        with pytest.raises(App.DoesNotExist):  # noqa: F405
            App.objects.get(name=data["name"])


@pytest.mark.parametrize(
    "url, valid",
    [
        ("https://example.com/repo", False),
        ("https://github.com/someorg/repo", False),
        ("https://github.com/ministryofjustice", False),
        ("http://github.com/ministryofjustice/nothttps", False),
        ("https://github.com/ministryofjustice/success", True),
    ],
)
def test_validate_repo_url(url, valid):
    serializer = AppSerializer()
    if valid:
        assert serializer.validate_repo_url(url) == url
    else:
        with pytest.raises(ValidationError):
            serializer.validate_repo_url(url)
