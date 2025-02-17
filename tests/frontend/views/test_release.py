# Standard library
from unittest import mock

# Third-party
import pytest
from django.urls import reverse
from pytest_django.asserts import assertQuerySetEqual

# First-party/Local
from controlpanel.api.models.tool import Tool
from controlpanel.frontend.views import release


@pytest.fixture
def release_data(users):
    return {
        "name": "test-release",
        "version": "1.0",
        "image_tag": "1.1",
        "chart_name": "rstudio",
        "description": "test",
        "target_users_list": f"{users['normal_user'].username}, {users['superuser'].username}",
        "values": '{"client_id": "id", "client_secret": "secret"}',
    }


def test_release_detail_context_data():
    """
    Ensure the context data for the release detail view contains the expected
    list of beta users (if they exist).
    """
    v = release.ReleaseDetail()
    v.request = mock.MagicMock()
    v.request.method = "GET"
    mock_object = mock.MagicMock()
    mock_user1 = mock.MagicMock()
    mock_user2 = mock.MagicMock()
    mock_user1.username = "aldo"
    mock_user2.username = "nicholas"
    mock_object.target_users.all.return_value = [mock_user1, mock_user2]
    v.object = mock_object
    result = v.get_context_data()
    assert result["target_users"] == "aldo, nicholas"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "data, count",
    [
        ({}, 2),
        ({"chart_name": "rstudio"}, 1),
        ({"chart_name": "jupyter-lab"}, 1),
        ({"status": "restricted"}, 0),
        ({"status": "active"}, 2),
    ],
)
def test_release_list_get_context_data(rf, data, count):
    """
    Note: ToolRelease objects are created in data migration api/migrations/0010_DATA_add_tools.py
    """
    view = release.ReleaseList()
    view.request = rf.get("/releases/", data=data)
    view.object_list = view.get_queryset()
    context = view.get_context_data()

    assert "filter" in context
    assert "releases" in context
    assertQuerySetEqual(context["releases"], context["filter"].qs.distinct())
    assert context["releases"].count() == count


@pytest.mark.django_db
def test_release_create_success(client, users, release_data):
    """
    Ensure the release is created successfully.
    """
    client.force_login(users["superuser"])
    url = reverse("create-tool-release")
    response = client.get(url)
    assert response.status_code == 200

    response = client.post(
        url,
        data=release_data,
    )
    assert response.status_code == 302
    assert response.url == reverse("list-tool-releases")

    response = client.get(reverse("list-tool-releases"))
    assert b"test-release" in response.content

    tool = Tool.objects.get(
        name=release_data["name"],
        version=release_data["version"],
        image_tag=release_data["image_tag"],
        description=release_data["description"],
    )
    target_users_list = release_data.pop("target_users_list")
    assert tool.target_users.count() == 2
    assert set(tool.target_users.values_list("username", flat=True)) == set(
        target_users_list.split(", ")
    )


@pytest.mark.django_db
def test_release_create_failure(client, users, release_data):
    """
    Ensure the release is not created if target users not valid
    """
    client.force_login(users["superuser"])
    url = reverse("create-tool-release")
    response = client.get(url)
    assert response.status_code == 200

    release_data["target_users_list"] = "invaliduser"

    response = client.post(
        url,
        data=release_data,
    )
    assert response.status_code == 200
    assert "target_users_list" in response.context_data["form"].errors


@pytest.mark.django_db
def test_release_update_success(client, users, release_data):
    """
    Ensure the release can be updated successfully.
    """
    client.force_login(users["superuser"])
    url = reverse("create-tool-release")
    response = client.get(url)
    assert response.status_code == 200

    target_users_list = release_data.pop("target_users_list")

    response = client.post(
        url,
        data=release_data,
    )
    tool = Tool.objects.get(
        name=release_data["name"],
        version=release_data["version"],
        image_tag=release_data["image_tag"],
        description=release_data["description"],
    )
    assert response.status_code == 302
    assert tool.target_users.count() == 0

    release_data["target_users_list"] = target_users_list
    response = client.post(
        reverse("manage-tool-release", kwargs={"pk": tool.pk}),
        data=release_data,
    )
    assert response.status_code == 302
    assert tool.target_users.count() == 2
    assert set(tool.target_users.values_list("username", flat=True)) == set(
        target_users_list.split(", ")
    )


@pytest.mark.django_db
def test_release_update_failure(client, users, release_data):
    """
    Ensure the release update fails when the target users are not valid
    """
    client.force_login(users["superuser"])
    url = reverse("create-tool-release")
    response = client.get(url)
    assert response.status_code == 200

    response = client.post(
        url,
        data=release_data,
    )
    tool = Tool.objects.get(
        name=release_data["name"],
        version=release_data["version"],
        image_tag=release_data["image_tag"],
        description=release_data["description"],
    )
    release_data["target_users_list"] = "invaliduser"
    response = client.post(
        reverse("manage-tool-release", kwargs={"pk": tool.pk}),
        data=release_data,
    )
    assert response.status_code == 200
    assert "target_users_list" in response.context_data["form"].errors


@mock.patch("controlpanel.api.models.Tool.uninstall_deployments")
def test_retire_release(uninstall_deployments, client, users, release_data):
    """
    Ensure retiring the release uninstalls deployments.
    """
    client.force_login(users["superuser"])
    # create the tool
    response = client.post(
        reverse("create-tool-release"),
        data=release_data,
    )
    tool = Tool.objects.get(
        name=release_data["name"],
        version=release_data["version"],
        image_tag=release_data["image_tag"],
        description=release_data["description"],
    )

    # retire the tool
    url = reverse("manage-tool-release", kwargs={"pk": tool.pk})
    release_data["is_retired"] = True
    response = client.post(url, data=release_data)

    uninstall_deployments.assert_called_once()
    tool.refresh_from_db()
    assert tool.is_retired is True
    assert response.status_code == 302
    assert response.url == reverse("list-tool-releases")
