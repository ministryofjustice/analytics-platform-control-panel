# Standard library
import json
from subprocess import CalledProcessError
from unittest.mock import patch

# Third-party
import pytest
from botocore.exceptions import ClientError
from model_bakery import baker
from rest_framework import status
from rest_framework.reverse import reverse

# First-party/Local
from controlpanel.api.models import User
from controlpanel.api.tasks.user import upgrade_user_helm_chart


@pytest.fixture(autouse=True)
def models(users):
    with patch("controlpanel.api.aws.AWSBucket.create"):
        baker.make("api.UserS3Bucket", user=users["normal_user"])
        baker.make("api.UserApp", user=users["normal_user"])


@pytest.fixture
def ExtendedAuth0():
    with patch("controlpanel.api.models.app.auth0.ExtendedAuth0") as authz:
        yield authz.return_value


def test_list(client, users):
    response = client.get(reverse("user-list"))
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data["results"]) == 9


def test_detail(client, users):
    response = client.get(reverse("user-detail", (users["normal_user"].auth0_id,)))
    assert response.status_code == status.HTTP_200_OK

    expected_fields = {
        "auth0_id",
        "url",
        "username",
        "name",
        "email",
        "justice_email",
        "groups",
        "userapps",
        "users3buckets",
        "is_superuser",
        "email_verified",
    }
    assert expected_fields == set(response.data)

    userapp = response.data["userapps"][0]
    expected_fields = {"id", "app", "is_admin"}
    assert set(userapp) == expected_fields

    expected_fields = {
        "id",
        "url",
        "name",
        "description",
        "slug",
        "repo_url",
        "iam_role_name",
        "created_by",
    }
    assert set(userapp["app"]) == expected_fields

    users3bucket = response.data["users3buckets"][0]
    expected_fields = {"id", "s3bucket", "access_level", "is_admin"}
    assert set(users3bucket) == expected_fields

    expected_fields = {
        "id",
        "url",
        "name",
        "arn",
        "created_by",
        "is_data_warehouse",
    }
    assert set(users3bucket["s3bucket"]) == expected_fields


def test_delete(client, helm, users, ExtendedAuth0):
    with patch("controlpanel.api.aws.AWSRole.delete_role") as delete_role:
        response = client.delete(reverse("user-detail", (users["normal_user"].auth0_id,)))
        assert response.status_code == status.HTTP_204_NO_CONTENT

        delete_role.assert_called()
        helm.delete.assert_called()

        ExtendedAuth0.clear_up_user.assert_called_with(user_id=users["normal_user"].auth0_id)

        response = client.get(reverse("user-detail", (users["normal_user"].auth0_id,)))
        assert response.status_code == status.HTTP_404_NOT_FOUND


def test_create(client, helm):
    with patch("controlpanel.api.aws.AWSRole.create_role") as create_user_role:
        data = {"auth0_id": "github|3", "username": "foo"}
        response = client.post(reverse("user-list"), data)
        assert response.status_code == status.HTTP_201_CREATED

        assert response.data["auth0_id"] == data["auth0_id"]

        create_user_role.assert_called()
        helm.upgrade_release.assert_called()


@pytest.fixture(autouse=True)
def slack():
    with patch("controlpanel.api.models.user.slack") as slack:
        yield slack


def test_create_superuser(client, slack, superuser):
    data = {"auth0_id": "github|3", "username": "foo", "is_superuser": True}
    response = client.post(reverse("user-list"), data)
    assert response.status_code == status.HTTP_201_CREATED

    slack.notify_superuser_created.assert_called_with(
        data["username"],
        by_username=superuser.username,
    )


def test_update(client, users):
    data = {"username": "foo", "auth0_id": users["normal_user"].auth0_id}
    response = client.put(
        reverse("user-detail", (users["normal_user"].auth0_id,)),
        json.dumps(data),
        content_type="application/json",
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.data["username"] == data["username"]
    assert response.data["auth0_id"] == data["auth0_id"]


def test_update_grants_superuser_access(client, users, slack, superuser):
    user = users["normal_user"]
    data = {"username": user.username, "auth0_id": user.auth0_id, "is_superuser": True}
    response = client.put(
        reverse("user-detail", (user.auth0_id,)),
        json.dumps(data),
        content_type="application/json",
    )
    assert response.status_code == status.HTTP_200_OK
    slack.notify_superuser_created.assert_called_with(user.username, by_username=superuser.username)


def test_aws_error_and_transaction(client, helm):
    with patch("controlpanel.api.aws.AWSRole.create_role") as create_user_role:
        create_user_role.side_effect = ClientError({"foo": "bar"}, "bar")
        data = {"auth0_id": "github|3", "username": "foo"}

        helm.reset_mock()

        with pytest.raises(ClientError):
            client.post(reverse("user-list"), data)

        create_user_role.assert_called()
        helm.upgrade_release.assert_not_called()

        with pytest.raises(User.DoesNotExist):
            User.objects.get(pk=data["auth0_id"])


def test_helm_error_and_transaction(client, helm):
    with patch("controlpanel.api.aws.AWSRole.create_role") as create_user_role:
        helm.upgrade_release.side_effect = CalledProcessError(1, "Helm error")
        data = {"auth0_id": "github|3", "username": "foo"}

        with pytest.raises(CalledProcessError):
            client.post(reverse("user-list"), data)

        create_user_role.assert_called()
        helm.upgrade_release.assert_called()

        with pytest.raises(User.DoesNotExist):
            User.objects.get(pk=data["auth0_id"])
