from operator import itemgetter
import re

from django.contrib.auth.models import Group
from rest_framework import serializers

from control_panel_api.models import (
    App,
    AppS3Bucket,
    S3Bucket,
    User,
    UserApp,
    UserS3Bucket,
)


class GroupSerializer(serializers.ModelSerializer):

    class Meta:
        model = Group
        fields = ('id', 'url', 'name')


class AppS3BucketSerializer(serializers.ModelSerializer):

    class Meta:
        model = AppS3Bucket
        fields = ('id', 'url', 'app', 's3bucket', 'access_level')

    def update(self, instance, validated_data):
        if instance.app != validated_data['app']:
            raise serializers.ValidationError(
                "App is not editable. Create a new record."
            )
        if instance.s3bucket != validated_data['s3bucket']:
            raise serializers.ValidationError(
                "S3Bucket is not editable. Create a new record."
            )

        return super().update(instance, validated_data)

    def create(self, validated_data):
        if validated_data['s3bucket'].is_data_warehouse:
            raise serializers.ValidationError(
                'Apps cannot access data warehouse S3 Buckets.'
            )

        return super().create(validated_data)


class UserS3BucketSerializer(serializers.ModelSerializer):

    class Meta:
        model = UserS3Bucket
        fields = ('id', 'url', 'user', 's3bucket', 'access_level', 'is_admin')

    def update(self, instance, validated_data):
        if instance.user != validated_data['user']:
            raise serializers.ValidationError(
                "User is not editable. Create a new record."
            )
        if instance.s3bucket != validated_data['s3bucket']:
            raise serializers.ValidationError(
                "S3Bucket is not editable. Create a new record."
            )

        return super().update(instance, validated_data)


class AppSimpleSerializer(serializers.ModelSerializer):

    class Meta:
        model = App
        fields = (
            'id',
            'url',
            'name',
            'description',
            'slug',
            'repo_url',
            'iam_role_name',
            'created_by',
        )


class S3BucketSimpleSerializer(serializers.ModelSerializer):

    class Meta:
        model = S3Bucket
        fields = ('id', 'url', 'name', 'arn', 'created_by', 'is_data_warehouse')


class AppS3BucketNestedInAppSerializer(serializers.ModelSerializer):
    """Used from within with AppSerializer to not expose app"""
    s3bucket = S3BucketSimpleSerializer()

    class Meta:
        model = AppS3Bucket
        fields = ('id', 'url', 's3bucket', 'access_level')


class AppS3BucketNestedInS3BucketSerializer(serializers.ModelSerializer):
    """Used from within with S3BucketSerializer to not expose s3bucket"""
    app = AppSimpleSerializer()

    class Meta:
        model = AppS3Bucket
        fields = ('id', 'url', 'app', 'access_level')


class UserSimpleSerializer(serializers.ModelSerializer):

    class Meta:
        model = User
        fields = (
            'auth0_id',
            'url',
            'username',
            'name',
            'email',
        )


class UserAppNestedInAppSerializer(serializers.ModelSerializer):
    """Used from within with AppSerializer to explicitly expose the user
    but hide the app
    """
    user = UserSimpleSerializer()

    class Meta:
        model = UserApp
        fields = ('id', 'user', 'is_admin')


class AppSerializer(serializers.ModelSerializer):
    userapps = UserAppNestedInAppSerializer(many=True, read_only=True)
    apps3buckets = AppS3BucketNestedInAppSerializer(many=True, read_only=True)

    class Meta:
        model = App
        fields = (
            'id',
            'url',
            'name',
            'description',
            'slug',
            'repo_url',
            'iam_role_name',
            'created_by',
            'apps3buckets',
            'userapps',
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
        fields = ('id', 'user', 'access_level', 'is_admin')


class S3BucketSerializer(serializers.ModelSerializer):
    apps3buckets = AppS3BucketNestedInS3BucketSerializer(
        many=True, read_only=True)
    users3buckets = UserS3BucketNestedInS3BucketSerializer(
        many=True, read_only=True)

    class Meta:
        model = S3Bucket
        fields = (
            'id',
            'url',
            'name',
            'arn',
            'apps3buckets',
            'users3buckets',
            'created_by',
            'is_data_warehouse',
            'location_url',
        )
        read_only_fields = (
            'apps3buckets',
            'users3buckets',
            'created_by',
            'url',
        )


class UserAppSerializer(serializers.ModelSerializer):

    class Meta:
        model = UserApp
        fields = ('id', 'url', 'app', 'user', 'is_admin')

    def update(self, instance, validated_data):
        if instance.user != validated_data['user']:
            raise serializers.ValidationError(
                "User is not editable. Create a new record."
            )
        if instance.app != validated_data['app']:
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
        fields = ('id', 'app', 'is_admin')


class UserS3BucketNestedInUserSerializer(serializers.ModelSerializer):
    """Used from within with UserSerializer to explicitly expose the s3bucket
    but hide the User
    """
    s3bucket = S3BucketSimpleSerializer()

    class Meta:
        model = UserS3Bucket
        fields = ('id', 's3bucket', 'access_level', 'is_admin')


class UserSerializer(serializers.ModelSerializer):
    userapps = UserAppNestedInUserSerializer(many=True, read_only=True)
    users3buckets = UserS3BucketNestedInUserSerializer(
        many=True, read_only=True)

    class Meta:
        model = User
        fields = (
            'auth0_id',
            'url',
            'username',
            'name',
            'email',
            'groups',
            'userapps',
            'users3buckets',
            'is_superuser',
            'email_verified',
        )


class AppCustomerSerializer(serializers.Serializer):
    email = serializers.EmailField()
    user_id = serializers.CharField(max_length=64, required=False)
    nickname = serializers.CharField(max_length=64, required=False)
    name = serializers.CharField(max_length=64, required=False)

    class Meta:
        read_only_fields = (
            'user_id',
            'nickname',
            'name',
        )


class ESBucketHitsSerializer(serializers.BaseSerializer):

    def to_representation(self, aggregations):
        accessed_by_sum_map = {}
        accessed_by_type_map = {}

        for result in aggregations.bucket_hits:
            role_type, accessed_by = self._extract_fields(result.key)

            accessed_by_type_map[accessed_by] = role_type

            if accessed_by not in accessed_by_sum_map:
                accessed_by_sum_map[accessed_by] = result.doc_count
            else:
                accessed_by_sum_map[accessed_by] += result.doc_count

        results = [
            {'accessed_by': k, 'count': v, 'type': accessed_by_type_map[k]}
            for k, v in accessed_by_sum_map.items()
        ]

        sorted_by_sum = sorted(results, key=itemgetter('count'), reverse=True)

        return sorted_by_sum

    def _extract_fields(self, key):
        match = re.search('alpha_(app|user)_([\w-]+)/', key)

        if match:
            return match.group(1), match.group(2)

        return 'unknown', key


class S3BucketAccessLogsQueryParamsSerializer(serializers.Serializer):
    day_range = serializers.IntegerField(required=False)
