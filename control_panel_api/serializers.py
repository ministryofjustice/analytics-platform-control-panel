from django.contrib.auth.models import Group
from rest_framework import serializers

from control_panel_api.models import (
    App,
    AppS3Bucket,
    S3Bucket,
    User,
    UserS3Bucket)


class UserSerializer(serializers.ModelSerializer):

    class Meta:
        model = User
        fields = ('id', 'url', 'username', 'name', 'email', 'groups')


class GroupSerializer(serializers.ModelSerializer):

    class Meta:
        model = Group
        fields = ('id', 'url', 'name')


class AppSerializer(serializers.ModelSerializer):
    class Meta:
        model = App
        fields = (
            'id',
            'url',
            'name',
            'slug',
            'repo_url',
            'apps3buckets',
            'created_by',
        )


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


class UserS3BucketSerializer(serializers.ModelSerializer):

    class Meta:
        model = UserS3Bucket
        fields = ('id', 'url', 'user', 's3bucket', 'access_level')

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


class S3BucketSerializer(serializers.ModelSerializer):

    class Meta:
        model = S3Bucket
        fields = ('id', 'url', 'name', 'arn', 'apps3buckets', 'created_by')
