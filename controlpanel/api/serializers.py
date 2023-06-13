# Standard library
import re
from collections import defaultdict
from operator import itemgetter

# Third-party
from django.conf import settings
from rest_framework import serializers

# First-party/Local
from controlpanel.api import cluster
from controlpanel.api.models import (
    App,
    AppS3Bucket,
    IPAllowlist,
    S3Bucket,
    User,
    UserApp,
    UserS3Bucket,
)


class AppS3BucketSerializer(serializers.ModelSerializer):
    class Meta:
        model = AppS3Bucket
        fields = ("id", "url", "app", "s3bucket", "access_level")

    def update(self, instance, validated_data):
        if instance.app != validated_data["app"]:
            raise serializers.ValidationError(
                "App is not editable. Create a new record."
            )
        if instance.s3bucket != validated_data["s3bucket"]:
            raise serializers.ValidationError(
                "S3Bucket is not editable. Create a new record."
            )

        return super().update(instance, validated_data)

    def create(self, validated_data):
        if validated_data["s3bucket"].is_data_warehouse:
            raise serializers.ValidationError(
                "Apps cannot access data warehouse S3 Buckets."
            )

        return super().create(validated_data)


class UserS3BucketSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserS3Bucket
        fields = ("id", "url", "user", "s3bucket", "access_level", "is_admin")

    def update(self, instance, validated_data):
        user = instance.user
        s3bucket = instance.s3bucket
        if user != validated_data.get("user", user):
            raise serializers.ValidationError(
                "User is not editable. Create a new record."
            )
        if s3bucket != validated_data.get("s3bucket", s3bucket):
            raise serializers.ValidationError(
                "S3Bucket is not editable. Create a new record."
            )

        return super().update(instance, validated_data)


class AppSimpleSerializer(serializers.ModelSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name='app-detail',
        lookup_field='res_id'
    )

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
    url = serializers.HyperlinkedIdentityField(
        view_name='app-detail',
        lookup_field='res_id'
    )

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
        )
        read_only_fields = (
            "apps3buckets",
            "users3buckets",
            "created_by",
            "url",
        )


class UserAppSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserApp
        fields = ("id", "url", "app", "user", "is_admin")

    def update(self, instance, validated_data):
        if instance.user != validated_data["user"]:
            raise serializers.ValidationError(
                "User is not editable. Create a new record."
            )
        if instance.app != validated_data["app"]:
            raise serializers.ValidationError(
                "App is not editable. Create a new record."
            )

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


class ToolDeploymentSerializer(serializers.Serializer):
    old_chart_name = serializers.CharField(max_length=64, required=False)
    version = serializers.CharField(max_length=64, required=True)

    def validate_version(self, value):
        try:
            _, _, _ = value.split("__")
        except ValueError:
            raise serializers.ValidationError(
                "This field include chart name, version and tool.id,"
                ' they are joined by "__".'
            )


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
            "edit_link": "update-app-ip-allowlists"
        },
        cluster.App.AUTH0_CONNECTIONS: {
            "permission_flag": "api.create_app",
            "edit_link": "update-auth0-connections"
        }
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
        return str(auth_flag.get('value') or 'true').lower() == 'true'

    def _process_existing_env_settings(self, app_auth_settings, auth_settings_status):
        for env_name, env_data in app_auth_settings.items():
            # Preparing secret data
            self._add_auth0_connection_as_part_secrets(
                env_name, env_data["secrets"], env_data["connections"])
            secret_data = self._process_secret_with_ui_info(env_data["secrets"])
            # Preparing env data
            var_data = self._process_env_with_ui_info(env_data["variables"])

            auth_required = self._auth_required(var_data.get(cluster.App.AUTHENTICATION_REQUIRED) or {})
            # The client exists in app_conf field and auth0
            created = auth_settings_status.get(env_name, {}).get('ok') or False
            # The client_id secret exists in github repo
            secret_existed = secret_data[cluster.App.AUTH0_CLIENT_ID]["created"]
            # The client_id exists in app_conf field
            conf_existed = auth_settings_status.get(env_name, {}).get("client_id")

            # Clear up redundant settings
            if not auth_required and not secret_existed:
                self._remove_redundant_settings(secret_data, var_data)

            env_data["secrets"] = sorted(secret_data.values(), key=lambda x: x["name"])
            env_data["can_create_client"] = auth_required and not created
            env_data["can_remove_client"] = not auth_required and \
                                            (created or secret_existed or conf_existed)
            env_data["variables"] = sorted(var_data.values(), key=lambda  x: x["name"])
            env_data["auth_required"] = auth_required


    def _process_redundant_envs(self, app_auth_settings, auth_settings_status):
        redundant_envs = list(set(auth_settings_status.keys()) -
                              set(app_auth_settings.keys()))
        for env_name in redundant_envs:
            app_auth_settings[env_name] = dict(is_redundant=True)

    def _remove_redundant_settings(self, secret_data, var_data):
        removal_settings = [
            cluster.App.AUTH0_CLIENT_ID,
            cluster.App.AUTH0_CLIENT_SECRET,
            cluster.App.AUTH0_CONNECTIONS,
            cluster.App.AUTH0_PASSWORDLESS,
            cluster.App.AUTH0_DOMAIN
        ]
        for item in removal_settings:
            if item in secret_data and not secret_data[item].get('value'):
                del secret_data[item]
            if item in var_data and not var_data[item].get('value'):
                del var_data[item]

    def _process_auth_settings(self, app_auth_settings, auth_settings_status):
        self._process_existing_env_settings(app_auth_settings, auth_settings_status)
        self._process_redundant_envs(app_auth_settings, auth_settings_status)
        return app_auth_settings

    def _process_secret_with_ui_info(self, secret_data):
        restructure_data = {}
        for item in secret_data:
            item_key = item['name']
            item.update(dict(
                display_name=cluster.App.get_github_key_display_name(item_key),
                permission_flag=self.APP_SETTINGS.get(item_key, {}).get('permission_flag') or
                                self.DEFAULT_PERMISSION_FLAG,
                edit_link=self.APP_SETTINGS.get(item_key, {}).get('edit_link') or
                          self.DEFAULT_EDIT_SECRET_LINK,
                remove_link=self.APP_SETTINGS.get(item_key, {}).get('remove_link') or
                            self.DEFAULT_REMOVE_SECRET_LINK
            ))
            restructure_data[item_key] = item
        return restructure_data

    def _process_env_with_ui_info(self, env_data):
        restructure_data = {}
        for item in env_data:
            item.update(dict(
                display_name=cluster.App.get_github_key_display_name(item['name']),
                permission_flag=self.DEFAULT_PERMISSION_FLAG,
                edit_link=self.DEFAULT_EDIT_ENV_LINK,
                remove_link=self.DEFAULT_REMOVE_ENV_LINK
            ))
            restructure_data[item['name']] = item
        return restructure_data

    def to_representation(self, app_auth_data):
        auth_settings = app_auth_data["auth_settings"]
        auth_settings_status = app_auth_data["auth0_clients_status"]
        return self._process_auth_settings(auth_settings, auth_settings_status)
