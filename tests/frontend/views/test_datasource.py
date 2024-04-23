# Standard library
from unittest.mock import patch

# Third-party
import pytest
from django.conf import settings
from django.urls import reverse, reverse_lazy
from model_bakery import baker
from rest_framework import status

# First-party/Local
from controlpanel.api.models import S3Bucket, UserS3Bucket
from controlpanel.frontend.forms import CreateDatasourceFolderForm, CreateDatasourceForm
from controlpanel.frontend.views import CreateDatasource


@pytest.fixture(autouse=True)
def enable_db_for_all_tests(db):
    pass


@pytest.fixture
def users(users):
    users.update(
        {
            "bucket_viewer": baker.make("api.User", username="bucket_viewer"),
            "bucket_admin": baker.make("api.User", username="bucket_admin"),
        }
    )
    return users


@pytest.fixture(autouse=True)
def buckets(db):
    with patch("controlpanel.api.aws.AWSBucket.create"):
        return {
            "app_data1": baker.make("api.S3Bucket", is_data_warehouse=False),
            "app_data2": baker.make("api.S3Bucket", is_data_warehouse=False),
            "warehouse1": baker.make("api.S3Bucket", is_data_warehouse=True),
            "warehouse2": baker.make("api.S3Bucket", is_data_warehouse=True),
            "other": baker.make("api.S3Bucket"),
        }


@pytest.fixture(autouse=True)
def users3buckets(buckets, users):
    return {
        "app_data_admin": baker.make(
            "api.UserS3Bucket",
            user=users["bucket_admin"],
            s3bucket=buckets["app_data1"],
            access_level=UserS3Bucket.READWRITE,
            is_admin=True,
        ),
        "app_data_admin2": baker.make(
            "api.UserS3Bucket",
            user=users["bucket_admin"],
            s3bucket=buckets["app_data2"],
            access_level=UserS3Bucket.READWRITE,
            is_admin=True,
        ),
        "app_data_readonly": baker.make(
            "api.UserS3Bucket",
            user=users["bucket_viewer"],
            s3bucket=buckets["app_data2"],
            access_level=UserS3Bucket.READONLY,
            is_admin=False,
        ),
        "warehouse_admin": baker.make(
            "api.UserS3Bucket",
            s3bucket=buckets["warehouse1"],
            user=users["bucket_admin"],
            access_level=UserS3Bucket.READWRITE,
            is_admin=True,
        ),
        "warehouse_admin2": baker.make(
            "api.UserS3Bucket",
            s3bucket=buckets["warehouse2"],
            user=users["bucket_admin"],
            access_level=UserS3Bucket.READWRITE,
            is_admin=True,
        ),
        "warehouse_readonly": baker.make(
            "api.UserS3Bucket",
            s3bucket=buckets["warehouse1"],
            user=users["bucket_viewer"],
            access_level=UserS3Bucket.READONLY,
            is_admin=False,
        ),
    }


def list_warehouse(client, *args):
    return client.get(reverse("list-warehouse-datasources"))


def list_app_data(client, *args):
    return client.get(reverse("list-webapp-datasources"))


def list_all(client, *args):
    return client.get(reverse("list-all-datasources"))


def detail(client, buckets, *args, bucket=None):
    bucket = bucket or buckets["warehouse1"]
    return client.get(reverse("manage-datasource", kwargs={"pk": bucket.id}))


def create(client, *args, **kwargs):
    name = kwargs.pop("name", "test-new-bucket")
    data = {
        "name": name,
    }
    return client.post(reverse("create-datasource") + "?type=warehouse", data)


def delete(client, buckets, *args, bucket=None):
    bucket = bucket or buckets["warehouse1"]
    return client.post(reverse("delete-datasource", kwargs={"pk": bucket.id}))


@pytest.mark.parametrize(
    "view,user,expected_status",
    [
        (list_warehouse, "superuser", status.HTTP_200_OK),
        (list_warehouse, "bucket_admin", status.HTTP_200_OK),
        (list_warehouse, "normal_user", status.HTTP_200_OK),
        (list_app_data, "superuser", status.HTTP_200_OK),
        (list_app_data, "bucket_admin", status.HTTP_200_OK),
        (list_app_data, "normal_user", status.HTTP_200_OK),
        (list_all, "superuser", status.HTTP_200_OK),
        (list_all, "bucket_admin", status.HTTP_403_FORBIDDEN),
        (list_all, "normal_user", status.HTTP_403_FORBIDDEN),
        (detail, "superuser", status.HTTP_200_OK),
        (detail, "bucket_admin", status.HTTP_200_OK),
        (detail, "normal_user", status.HTTP_403_FORBIDDEN),
        (create, "superuser", status.HTTP_302_FOUND),
        (create, "bucket_admin", status.HTTP_302_FOUND),
        (create, "normal_user", status.HTTP_302_FOUND),
        (delete, "superuser", status.HTTP_302_FOUND),
        (delete, "bucket_admin", status.HTTP_302_FOUND),
        (delete, "normal_user", status.HTTP_403_FORBIDDEN),
    ],
)
def test_bucket_permissions(client, buckets, users, view, user, expected_status):
    client.force_login(users[user])
    response = view(client, buckets, users)
    assert response.status_code == expected_status


def update_access(client, users3buckets, users, *args):
    data = {
        "entity_id": users["bucket_viewer"].auth0_id,
        "access_level": UserS3Bucket.READWRITE,
        "is_admin": False,
        "entity_type": "user",
    }
    return client.post(
        reverse(
            "update-access-level",
            kwargs={"pk": users3buckets["warehouse_readonly"].id},
        ),
        data,
    )


def revoke_access(client, users3buckets, *args):
    return client.post(
        reverse(
            "revoke-datasource-access",
            kwargs={"pk": users3buckets["warehouse_readonly"].id},
        )
    )


def grant_access(client, users3buckets, users, **kwargs):
    data = {
        "access_level": UserS3Bucket.READWRITE,
        "is_admin": False,
        "entity_id": users["other_user"].auth0_id,
        "entity_type": "user",
    }
    data.update(**kwargs)
    return client.post(
        reverse(
            "grant-datasource-access",
            kwargs={"pk": users3buckets["warehouse_readonly"].s3bucket.id},
        ),
        data,
    )


@pytest.mark.parametrize(
    "view,user,expected_status",
    [
        (update_access, "superuser", status.HTTP_302_FOUND),
        (update_access, "bucket_admin", status.HTTP_302_FOUND),
        (update_access, "normal_user", status.HTTP_403_FORBIDDEN),
        (revoke_access, "superuser", status.HTTP_302_FOUND),
        (revoke_access, "bucket_admin", status.HTTP_302_FOUND),
        (revoke_access, "normal_user", status.HTTP_403_FORBIDDEN),
        (grant_access, "superuser", status.HTTP_302_FOUND),
        (grant_access, "bucket_admin", status.HTTP_302_FOUND),
        (grant_access, "normal_user", status.HTTP_403_FORBIDDEN),
    ],
)
def test_access_permissions(client, users3buckets, users, view, user, expected_status):
    client.force_login(users[user])
    response = view(client, users3buckets, users)
    assert response.status_code == expected_status


@pytest.mark.parametrize(
    "view,user,expected_count,show_deleted",
    [
        (list_warehouse, "superuser", 0, False),
        (list_warehouse, "normal_user", 0, False),
        (list_warehouse, "bucket_viewer", 1, False),
        (list_warehouse, "bucket_admin", 2, False),
        (list_app_data, "superuser", 0, False),
        (list_app_data, "normal_user", 0, False),
        (list_app_data, "bucket_viewer", 1, False),
        (list_app_data, "bucket_admin", 2, False),
        (list_all, "superuser", 5, True),
    ],
)
def test_list(client, buckets, users, view, user, expected_count, show_deleted):
    client.force_login(users[user])
    response = view(client, buckets, users)
    assert len(response.context_data["object_list"]) == expected_count
    assert ("deleted_datasources" in response.context_data) is show_deleted


@pytest.mark.parametrize(
    "view,user,n_other_datasources",
    [
        (list_warehouse, "superuser", 2),
        (list_warehouse, "normal_user", 2),
        (list_warehouse, "bucket_viewer", 1),
        (list_warehouse, "bucket_admin", 0),
        (list_app_data, "superuser", 3),
        (list_app_data, "normal_user", 3),
        (list_app_data, "bucket_viewer", 2),
        (list_app_data, "bucket_admin", 1),
    ],
)
def test_list_other_datasources(client, buckets, users, view, user, n_other_datasources):
    client.force_login(users[user])
    response = view(client, buckets, users)
    assert len(response.context_data["other_datasources"]) == n_other_datasources


def test_list_other_datasources_admins(client, buckets, users):
    bucket_admin = users["bucket_admin"]

    # Listing of "warehouse datasources"
    client.force_login(users["normal_user"])
    response = list_warehouse(client)

    other_datasources_admins = response.context_data["other_datasources_admins"]
    assert other_datasources_admins[buckets["warehouse1"].id] == [bucket_admin]
    assert other_datasources_admins[buckets["warehouse2"].id] == [bucket_admin]

    # Listing of "app datasources"
    client.force_login(users["normal_user"])
    response = list_app_data(client)

    other_datasources_admins = response.context_data["other_datasources_admins"]
    assert other_datasources_admins[buckets["app_data1"].id] == [bucket_admin]
    assert other_datasources_admins[buckets["app_data2"].id] == [bucket_admin]
    assert other_datasources_admins[buckets["other"].id] == []


@patch("controlpanel.api.models.users3bucket.tasks.S3BucketGrantToUser")
@patch("controlpanel.api.models.s3bucket.tasks.S3BucketCreate")
def test_bucket_creator_has_readwrite_and_admin_access(
    create_bucket_task, grant_user_task, client, users
):
    user = users["normal_user"]
    client.force_login(user)
    create(client)
    assert user.users3buckets.count() == 1
    ub = user.users3buckets.all()[0]
    assert ub.access_level == UserS3Bucket.READWRITE
    assert ub.is_admin
    create_bucket_task.assert_called_once()
    grant_user_task.assert_called_once()


@pytest.mark.parametrize(
    "folders_enabled, datasource_type, form_class",
    [
        (False, "", CreateDatasourceForm),
        (False, "webapp", CreateDatasourceForm),
        (True, "webapp", CreateDatasourceForm),
        (True, "", CreateDatasourceFolderForm),
    ],
)
def test_create_get_form_class(rf, folders_enabled, datasource_type, form_class):
    request = rf.get(f"/?type={datasource_type}")
    with patch("django.conf.settings.features.s3_folders") as s3_folders:
        s3_folders.enabled = folders_enabled
        view = CreateDatasource()
        view.request = request

        assert view.get_form_class() == form_class


@patch("controlpanel.api.models.users3bucket.tasks.S3BucketGrantToUser")
@patch("controlpanel.api.models.s3bucket.tasks.S3BucketCreate")
@patch("django.conf.settings.features.s3_folders.enabled", True)
@pytest.mark.parametrize("user", ["superuser", "normal_user", "other_user"])
def test_create_folders(
    create_bucket_task, grant_user_task, user, client, users, root_folder_bucket
):
    """
    Check that all users can create a folder datasource
    """
    user = users[user]
    client.force_login(user)
    folder_name = f"test-{user.username}-folder"
    response = create(client, name=folder_name)

    # redirect expected on success
    assert response.status_code == 302
    assert user.users3buckets.filter(
        s3bucket__name=f"{root_folder_bucket.name}/{folder_name}"
    ).exists()
    # make sure tasks are sent
    create_bucket_task.assert_called_once()
    grant_user_task.assert_called_once()

    # create another folder to catch any errors updating IAM policy
    create_bucket_task.reset_mock()
    grant_user_task.reset_mock()
    folder_name = f"test-{user.username}-folder-2"
    response = create(client, name=folder_name)

    # redirect expected on success
    assert response.status_code == 302
    assert user.users3buckets.filter(
        s3bucket__name=f"{root_folder_bucket.name}/{folder_name}"
    ).exists()
    # tasks to create are sent again for the second folder
    create_bucket_task.assert_called_once()
    grant_user_task.assert_called_once()


@patch("django.conf.settings.features.s3_folders.enabled", False)
def test_create_bucket_name_greater_than_63_fails(client, users):

    name = "test-bucket-" + ("x" * 52)
    assert len(name) == 64

    client.force_login(users["superuser"])
    response = create(client, name=name)

    assert response.status_code == 200
    assert S3Bucket.objects.filter(name=name).exists() is False


@patch("django.conf.settings.features.s3_folders.enabled", True)
def test_create_folder_name_greater_than_63_succeeds(client, users, root_folder_bucket):
    name = "test-folder-" + ("x" * 52)
    assert len(name) == 64

    client.force_login(users["superuser"])
    response = create(client, name=name)

    assert response.status_code == 302
    assert S3Bucket.objects.filter(name=f"{root_folder_bucket.name}/{name}").exists() is True


@pytest.mark.parametrize(
    "kwargs",
    [
        {"paths": ["/invalidpath/"]},
        {"entity_id": ""},
    ],
)
def test_grant_access_invalid_form(client, users3buckets, users, kwargs):
    """
    Regression test to check that the page renders when the form is invalid
    """
    client.force_login(users["superuser"])
    response = grant_access(client, users3buckets, users, **kwargs)

    assert response.status_code == 200
    assert response.context_data["form"].is_valid() is False


@pytest.mark.parametrize(
    "bucket, success_url",
    [
        ("warehouse1", reverse_lazy("list-warehouse-datasources")),
        ("app_data1", reverse_lazy("list-webapp-datasources")),
    ],
)
def test_delete_calls_soft_delete(
    client,
    buckets,
    users,
    bucket,
    success_url,
    sqs,
    helpers,
):
    admin = users["bucket_admin"]
    bucket = buckets[bucket]

    client.force_login(admin)
    response = delete(client, buckets, bucket=bucket)
    bucket.refresh_from_db()

    assert bucket.pk is not None
    assert bucket.is_deleted is True
    assert bucket.deleted_by == admin
    assert bucket.deleted_at is not None
    assert response.url == success_url

    messages = helpers.retrieve_messages(sqs, queue_name=settings.S3_QUEUE_NAME)
    helpers.validate_task_with_sqs_messages(
        messages,
        S3Bucket.__name__,
        bucket.id,
        queue_name=settings.S3_QUEUE_NAME,
    )


@pytest.mark.parametrize(
    "user, bucket, expected_status",
    [
        ("superuser", "app_data1", status.HTTP_200_OK),
        ("superuser", "app_data2", status.HTTP_200_OK),
        ("superuser", "warehouse1", status.HTTP_200_OK),
        ("superuser", "warehouse2", status.HTTP_200_OK),
        ("superuser", "other", status.HTTP_200_OK),
        ("bucket_viewer", "app_data1", status.HTTP_404_NOT_FOUND),
        ("bucket_viewer", "app_data2", status.HTTP_404_NOT_FOUND),
        ("bucket_viewer", "warehouse1", status.HTTP_404_NOT_FOUND),
        ("bucket_viewer", "warehouse2", status.HTTP_404_NOT_FOUND),
        ("bucket_viewer", "other", status.HTTP_404_NOT_FOUND),
        ("bucket_admin", "app_data1", status.HTTP_404_NOT_FOUND),
        ("bucket_admin", "app_data2", status.HTTP_404_NOT_FOUND),
        ("bucket_admin", "warehouse1", status.HTTP_404_NOT_FOUND),
        ("bucket_admin", "warehouse2", status.HTTP_404_NOT_FOUND),
        ("bucket_admin", "other", status.HTTP_404_NOT_FOUND),
    ],
)
def test_detail_for_deleted_datasource(client, buckets, users, user, bucket, expected_status):
    user = users[user]
    bucket = buckets[bucket]
    bucket.soft_delete(deleted_by=user)

    client.force_login(user)
    response = detail(client, user, bucket=bucket)

    assert response.status_code == expected_status
