# Standard library
import re
from collections import defaultdict
from functools import partial
from operator import itemgetter

# Third-party
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import EmailValidator
from django.db import transaction
from rest_framework import serializers

# First-party/Local
from controlpanel.api import cluster, validators
from controlpanel.api.models import (
    App,
    AppS3Bucket,
    Dashboard,
    IPAllowlist,
    S3Bucket,
    ToolDeployment,
    User,
    UserApp,
    UserS3Bucket,
)
from controlpanel.utils import start_background_task


class AppS3BucketSerializer(serializers.ModelSerializer):
    class Meta:
        model = AppS3Bucket
        fields = ("id", "url", "app", "s3bucket", "access_level")

    def update(self, instance, validated_data):
        if instance.app != validated_data["app"]:
            raise serializers.ValidationError("App is not editable. Create a new record.")
        if instance.s3bucket != validated_data["s3bucket"]:
            raise serializers.ValidationError("S3Bucket is not editable. Create a new record.")

        return super().update(instance, validated_data)

    def create(self, validated_data):
        if validated_data["s3bucket"].is_data_warehouse:
            raise serializers.ValidationError("Apps cannot access data warehouse S3 Buckets.")

        return super().create(validated_data)


class UserS3BucketSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserS3Bucket
        fields = ("id", "url", "user", "s3bucket", "access_level", "is_admin")

    def update(self, instance, validated_data):
        user = instance.user
        s3bucket = instance.s3bucket
        if user != validated_data.get("user", user):
            raise serializers.ValidationError("User is not editable. Create a new record.")
        if s3bucket != validated_data.get("s3bucket", s3bucket):
            raise serializers.ValidationError("S3Bucket is not editable. Create a new record.")

        return super().update(instance, validated_data)


class AppSimpleSerializer(serializers.ModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name="app-detail", lookup_field="res_id")

    class Meta:
        model = App
        fields = (
            "id",
            "url",
            "name",
            "description",
            "slug",
            "repo_url",
            "iam_role_name",
            "created_by",
        )


class IPAllowlistSimpleSerializer(serializers.ModelSerializer):
    class Meta:
        model = IPAllowlist
        fields = (
            "name",
            "description",
            "contact",
            "allowed_ip_ranges",
            "is_recommended",
        )


class S3BucketSimpleSerializer(serializers.ModelSerializer):
    class Meta:
        model = S3Bucket
        fields = ("id", "url", "name", "arn", "created_by", "is_data_warehouse")


class AppS3BucketNestedInAppSerializer(serializers.ModelSerializer):
    """Used from within with AppSerializer to not expose app"""

    s3bucket = S3BucketSimpleSerializer()

    class Meta:
        model = AppS3Bucket
        fields = ("id", "url", "s3bucket", "access_level")


class AppS3BucketNestedInS3BucketSerializer(serializers.ModelSerializer):
    """Used from within with S3BucketSerializer to not expose s3bucket"""

    app = AppSimpleSerializer()

    class Meta:
        model = AppS3Bucket
        fields = ("id", "url", "app", "access_level")


class UserSimpleSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            "auth0_id",
            "url",
            "username",
            "name",
            "email",
        )


class UserAppNestedInAppSerializer(serializers.ModelSerializer):
    """Used from within with AppSerializer to explicitly expose the user
    but hide the app
    """

    user = UserSimpleSerializer()

    class Meta:
        model = UserApp
        fields = ("id", "user", "is_admin")


class AppSerializer(serializers.ModelSerializer):
    userapps = UserAppNestedInAppSerializer(many=True, read_only=True)
    apps3buckets = AppS3BucketNestedInAppSerializer(many=True, read_only=True)
    ip_allowlists = IPAllowlistSimpleSerializer(many=True, read_only=True)
    url = serializers.HyperlinkedIdentityField(view_name="app-detail", lookup_field="res_id")

    class Meta:
        model = App
        # lookup_field = "id"
        fields = (
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
        )

    def validate_repo_url(self, value):
        """Normalise repo URLs by removing trailing .git"""
        try:
            validators.validate_github_repository_url(value)
        except ValidationError as e:
            raise serializers.ValidationError(e.message)
        return value.rsplit(".git", 1)[0]


class UserS3BucketNestedInS3BucketSerializer(serializers.ModelSerializer):
    """
    Serializer for `UserS3Bucket`s used within S3Bucket serializer.
    It exposes the `user` but not the `s3bucket` (which is the parent)
    """

    user = UserSimpleSerializer()

    class Meta:
        model = UserS3Bucket
        fields = ("id", "user", "access_level", "is_admin")


class S3BucketSerializer(serializers.ModelSerializer):
    apps3buckets = AppS3BucketNestedInS3BucketSerializer(many=True, read_only=True)
    users3buckets = UserS3BucketNestedInS3BucketSerializer(many=True, read_only=True)

    class Meta:
        model = S3Bucket
        fields = (
            "id",
            "url",
            "name",
            "arn",
            "apps3buckets",
            "users3buckets",
            "created_by",
            "is_data_warehouse",
            "location_url",
            "is_deleted",
            "deleted_by",
            "deleted_at",
        )
        read_only_fields = (
            "apps3buckets",
            "users3buckets",
            "created_by",
            "url",
            "is_deleted",
            "deleted_by",
            "deleted_at",
        )


class UserAppSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserApp
        fields = ("id", "url", "app", "user", "is_admin")

    def update(self, instance, validated_data):
        if instance.user != validated_data["user"]:
            raise serializers.ValidationError("User is not editable. Create a new record.")
        if instance.app != validated_data["app"]:
            raise serializers.ValidationError("App is not editable. Create a new record.")

        return super().update(instance, validated_data)


class UserAppNestedInUserSerializer(serializers.ModelSerializer):
    """Used from within with UserSerializer to explicitly expose the app
    but hide the User
    """

    app = AppSimpleSerializer()

    class Meta:
        model = UserApp
        fields = ("id", "app", "is_admin")


class UserS3BucketNestedInUserSerializer(serializers.ModelSerializer):
    """Used from within with UserSerializer to explicitly expose the s3bucket
    but hide the User
    """

    s3bucket = S3BucketSimpleSerializer()

    class Meta:
        model = UserS3Bucket
        fields = ("id", "s3bucket", "access_level", "is_admin")


class UserSerializer(serializers.ModelSerializer):
    userapps = UserAppNestedInUserSerializer(many=True, read_only=True)
    users3buckets = UserS3BucketNestedInUserSerializer(many=True, read_only=True)

    class Meta:
        model = User
        fields = (
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
        )


class AppCustomerSerializer(serializers.Serializer):
    email = serializers.CharField()
    user_id = serializers.CharField(max_length=64, required=False)
    nickname = serializers.CharField(max_length=64, required=False)
    name = serializers.CharField(max_length=64, required=False)

    class Meta:
        read_only_fields = (
            "user_id",
            "nickname",
            "name",
        )


class AppCustomersQueryParamsSerializer(serializers.Serializer):
    env_name = serializers.CharField(max_length=64, required=True)
    page = serializers.IntegerField(min_value=1, required=False, default=1)
    per_page = serializers.IntegerField(min_value=1, required=False, default=25)

    def __init__(self, *args, **kwargs):
        self.app = kwargs.pop("app")
        super().__init__(*args, **kwargs)

    def validate_env_name(self, env_name):
        if not self.app.get_group_id(env_name):
            raise serializers.ValidationError(f"{env_name} is invalid for this app.")
        return env_name


class AddAppCustomersSerializer(serializers.Serializer):
    emails = serializers.CharField(max_length=None, required=True)
    env_name = serializers.CharField(max_length=64, required=True)

    def __init__(self, *args, **kwargs):
        self.app = kwargs.pop("app")
        super().__init__(*args, **kwargs)

    def validate_emails(self, emails):
        delimiters = re.compile(r"[,; ]+")  # split by comma, semicolon, and space
        emails = delimiters.split(emails)
        errors = []
        validator = EmailValidator()
        for email in emails:
            try:
                validator(email)
            except ValidationError:
                errors.append(email)
        if errors:
            raise serializers.ValidationError(
                f"Request contains invalid emails: {', '.join(errors)}"
            )
        return emails

    def validate_env_name(self, env_name):
        if not self.app.get_group_id(env_name):
            raise serializers.ValidationError(f"{env_name} is invalid for this app.")
        return env_name


class DeleteAppCustomerSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    env_name = serializers.CharField(max_length=64, required=True)


class ToolDeploymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ToolDeployment
        fields = ("tool",)

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request")
        super().__init__(*args, **kwargs)

    def create(self, validated_data):
        tool = validated_data["tool"]

        with transaction.atomic():
            # get the currently active deployment
            previous_deployment = ToolDeployment.objects.filter(
                user=self.request.user, tool_type=tool.tool_type, is_active=True
            ).first()
            # mark all previous deployments for this tool type as inactive
            ToolDeployment.objects.filter(user=self.request.user, tool_type=tool.tool_type).update(
                is_active=False
            )
            # create the new active deployment record
            new_deployment = ToolDeployment.objects.create(
                tool=tool,
                tool_type=tool.tool_type,
                user=self.request.user,
            )

        # use these details to start a background process to uninstall the deploy the new tool
        # TODO we may want to refactor this to be handled by celery
        task = "tool.deploy"
        message = {
            "new_deployment_id": new_deployment.id,
            "previous_deployment_id": previous_deployment.id if previous_deployment else None,
            "id_token": self.request.user.get_id_token(),
        }
        task_func = partial(start_background_task, task=task, message=message)
        transaction.on_commit(task_func)
        return new_deployment


class ESBucketHitsSerializer(serializers.BaseSerializer):
    def to_representation(self, bucket_hits):
        access_count = defaultdict(int)
        accessor_role = {}

        for result in bucket_hits:
            role_type, accessed_by = self._get_accessed_by(result.key)

            accessor_role[accessed_by] = role_type
            access_count[accessed_by] += result.doc_count

        results = [
            {"accessed_by": k, "count": v, "type": accessor_role[k]}
            for k, v in access_count.items()
        ]

        return sorted(results, key=itemgetter("count"), reverse=True)

    def _get_accessed_by(self, key):
        match = re.search(rf"{settings.ENV}_(app|user)_([\w-]+)/", key)

        if match:
            return match.group(1), match.group(2)

        return "unknown", key


class ToolSerializer(serializers.Serializer):
    name = serializers.CharField()


class GithubItemSerializer(serializers.Serializer):
    html_url = serializers.CharField()
    full_name = serializers.CharField()


class AppAuthSettingsSerializer(serializers.BaseSerializer):
    DEFAULT_EDIT_SECRET_LINK = "update-app-secret"
    DEFAULT_REMOVE_SECRET_LINK = "delete-app-secret"
    DEFAULT_EDIT_ENV_LINK = "update-app-var"
    DEFAULT_REMOVE_ENV_LINK = "delete-app-var"
    DEFAULT_PERMISSION_FLAG = "api.update_app_settings"
    APP_SETTINGS = {
        cluster.App.IP_RANGES: {
            "permission_flag": "api.update_app_ip_allowlists",
            "edit_link": "update-app-ip-allowlists",
        },
        cluster.App.AUTH0_CONNECTIONS: {
            "permission_flag": "api.create_connections",
            "edit_link": "update-auth0-connections",
        },
    }

    def _add_auth0_connection_as_part_secrets(self, env_name, app_secrets, connections):
        app_secrets.append(
            {
                "name": cluster.App.AUTH0_CONNECTIONS,
                "env_name": env_name,
                "value": connections or [],
                "created": connections is not None,
                "removable": False,
                "editable": True,
            }
        )

    def _auth_required(self, auth_flag):
        return str(auth_flag.get("value") or "true").lower() == "true"

    def _process_existing_env_settings(self, app_auth_settings, auth_settings_status):
        for env_name, env_data in app_auth_settings.items():
            # Preparing secret data
            self._add_auth0_connection_as_part_secrets(
                env_name, env_data["secrets"], env_data["connections"]
            )
            secret_data = self._process_secret_with_ui_info(env_data["secrets"])
            # Preparing env data
            var_data = self._process_env_with_ui_info(env_data["variables"])

            auth_required = self._auth_required(
                var_data.get(cluster.App.AUTHENTICATION_REQUIRED) or {}
            )
            # The client exists in app_conf field and auth0
            created = auth_settings_status.get(env_name, {}).get("ok") or False
            # The client_id secret exists in github repo
            secret_existed = secret_data[cluster.App.AUTH0_CLIENT_ID]["created"]
            # The client_id exists in app_conf field
            conf_existed = auth_settings_status.get(env_name, {}).get("client_id")

            # Clear up redundant settings
            if not auth_required and not secret_existed:
                self._remove_redundant_settings(secret_data, var_data)

            env_data["secrets"] = sorted(secret_data.values(), key=lambda x: x["name"])
            env_data["can_create_client"] = auth_required and not created
            env_data["can_remove_client"] = not auth_required and (
                created or secret_existed or conf_existed
            )
            env_data["variables"] = sorted(var_data.values(), key=lambda x: x["name"])
            env_data["auth_required"] = auth_required

    def _process_redundant_envs(self, app_auth_settings, auth_settings_status):
        # NB. if earlier call to get app_auth_settings failed, this will have been
        # passed into serializer as an empty dict. Which results in all env details
        # being marked as redundant mistakenly
        redundant_envs = list(set(auth_settings_status.keys()) - set(app_auth_settings.keys()))
        for env_name in redundant_envs:
            app_auth_settings[env_name] = dict(is_redundant=True)

    def _remove_redundant_settings(self, secret_data, var_data):
        removal_settings = [
            cluster.App.AUTH0_CLIENT_ID,
            cluster.App.AUTH0_CLIENT_SECRET,
            cluster.App.AUTH0_CONNECTIONS,
            cluster.App.AUTH0_PASSWORDLESS,
            cluster.App.AUTH0_DOMAIN,
        ]
        for item in removal_settings:
            if item in secret_data and not secret_data[item].get("value"):
                del secret_data[item]
            if item in var_data and not var_data[item].get("value"):
                del var_data[item]

    def _process_auth_settings(self, app_auth_settings, auth_settings_status):
        self._process_existing_env_settings(app_auth_settings, auth_settings_status)
        self._process_redundant_envs(app_auth_settings, auth_settings_status)
        return app_auth_settings

    def _process_secret_with_ui_info(self, secret_data):
        restructure_data = {}
        for item in secret_data:
            item_key = item["name"]
            item.update(
                dict(
                    display_name=cluster.App.get_github_key_display_name(item_key),
                    permission_flag=self.APP_SETTINGS.get(item_key, {}).get("permission_flag")
                    or self.DEFAULT_PERMISSION_FLAG,
                    edit_link=self.APP_SETTINGS.get(item_key, {}).get("edit_link")
                    or self.DEFAULT_EDIT_SECRET_LINK,
                    remove_link=self.APP_SETTINGS.get(item_key, {}).get("remove_link")
                    or self.DEFAULT_REMOVE_SECRET_LINK,
                )
            )
            restructure_data[item_key] = item
        return restructure_data

    def _process_env_with_ui_info(self, env_data):
        restructure_data = {}
        for item in env_data:
            item.update(
                dict(
                    display_name=cluster.App.get_github_key_display_name(item["name"]),
                    permission_flag=self.DEFAULT_PERMISSION_FLAG,
                    edit_link=self.DEFAULT_EDIT_ENV_LINK,
                    remove_link=self.DEFAULT_REMOVE_ENV_LINK,
                )
            )
            restructure_data[item["name"]] = item
        return restructure_data

    def to_representation(self, app_auth_data):
        auth_settings = app_auth_data["auth_settings"]
        auth_settings_status = app_auth_data["auth0_clients_status"]
        return self._process_auth_settings(auth_settings, auth_settings_status)


class DashboardAdminSerializer(serializers.ModelSerializer):
    email = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ("name", "email")

    def get_email(self, obj):
        if obj.justice_email:
            return obj.justice_email

        return obj.email


class DashboardSerializer(serializers.ModelSerializer):
    admins = DashboardAdminSerializer(many=True, read_only=True)

    class Meta:
        model = Dashboard
        fields = ("name", "quicksight_id", "admins")


class DashboardUrlSerializer(DashboardSerializer):
    class Meta(DashboardSerializer.Meta):
        fields = ("name", "admins")

    def to_representation(self, dashboard):
        data = super().to_representation(dashboard)

        response = dashboard.get_embed_url()
        data["embed_url"] = response["EmbedUrl"]
        data["anonymous_user_arn"] = response["AnonymousUserArn"]
        return data
