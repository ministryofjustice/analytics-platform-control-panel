# Third-party
from django.db import transaction

# First-party/Local
from controlpanel.api import cluster
from controlpanel.api.models import (
    App,
    AppIPAllowList,
    AppS3Bucket,
    S3Bucket,
    UserApp,
    UserS3Bucket,
)
from controlpanel.utils import start_background_task


class AppManager:
    """
    This class is to manage some complex process for application entity.
    This steps for each process here may be re-structured into task-oriented pattern.
    The main intention for this class is to isolate the complicity from
    view classes, but somehow couldn't be fit in the django model pattern easily
    """

    def register_app(self, user, app_data):
        repo_url = app_data["repo_url"]
        _, name = repo_url.rsplit("/", 1)
        cloud_platform_role_arn = app_data.get("cloud_platform_role_arn", None)

        # Create app and all the related sources
        new_app = self._create_app(
            name=name,
            repo_url=repo_url,
            current_user=user,
            namespace=app_data["namespace"],
            cloud_platform_role_arn=cloud_platform_role_arn,
        )
        self._add_app_to_users(new_app, user)
        self._create_or_link_datasource(new_app, user, app_data)
        return new_app

    def trigger_tasks_for_ip_range_removal(self, user, deleted_object):
        affected_app_ids = list(
            AppIPAllowList.objects.filter(ip_allowlist_id=deleted_object.id)
            .values_list("app_id", flat=True)
            .distinct()
        )
        for app_id in affected_app_ids:
            start_background_task(
                "app_ip_ranges.delete",
                {
                    "user_id": user.id,
                    "app_id": app_id,
                    "ip_range_id": deleted_object.id,
                },
            )

    def _format_ip_string_to_list(self, ip_range_string):
        return set([item.strip() for item in ip_range_string.split(",")])

    def _has_ip_ranges_changed(self, old_ip_string, new_ip_string):
        old_set = self._format_ip_string_to_list(old_ip_string)
        new_set = self._format_ip_string_to_list(new_ip_string)
        return len(list(old_set - new_set)) > 0 or len(list(new_set - old_set)) > 0

    def trigger_tasks_for_ip_range_update(self, user, pre_update_obj, updated_obj):
        if self._has_ip_ranges_changed(
            pre_update_obj.allowed_ip_ranges, updated_obj.allowed_ip_ranges
        ):
            affected_app_ids = list(
                AppIPAllowList.objects.filter(ip_allowlist_id=updated_obj.id)
                .values_list("app_id", flat=True)
                .distinct()
            )
            for app_id in list(set(affected_app_ids)):
                start_background_task(
                    "app_ip_ranges.update", {"user_id": user.id, "app_id": app_id}
                )

    def _create_app(self, **kwargs):
        return App.objects.create(**kwargs)

    def _add_ip_allowlists(self, app, envs, ip_allowlists):
        for env in envs:
            AppIPAllowList.objects.update_records(app, env, ip_allowlists)

    def _create_or_link_datasource(self, app, user, bucket_data):
        if bucket_data.get("new_datasource_name"):
            bucket = S3Bucket.objects.create(
                name=bucket_data["new_datasource_name"],
                bucket_owner="APP",
                created_by=user,
            )
            AppS3Bucket.objects.create(
                app=app,
                s3bucket=bucket,
                access_level="readonly",
                current_user=user,
            )
        elif bucket_data.get("existing_datasource_id"):
            AppS3Bucket.objects.create(
                app=app,
                s3bucket=bucket_data["existing_datasource_id"],
                access_level="readonly",
                current_user=user,
            )

    def _add_app_to_users(self, app, user):
        UserApp.objects.create(
            app=app,
            user=user,
            is_admin=True,
        )

    def _create_app_role(self, app):
        cluster.App(app).create_iam_role()
