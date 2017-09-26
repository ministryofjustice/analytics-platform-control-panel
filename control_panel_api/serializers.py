from django.contrib.auth.models import Group
from rest_framework import serializers

from control_panel_api.models import (
    App,
    AppS3Bucket,
    S3Bucket,
    User
)


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
        fields = ('id', 'url', 'name', 'slug', 'repo_url', 'apps3buckets')


class AppS3BucketSerializer(serializers.ModelSerializer):

    class Meta:
        model = AppS3Bucket
        fields = ('id', 'url', 'app', 's3bucket', 'access_level')

    def update(self, instance, validated_data):
        if instance.app != validated_data['app']:
            raise serializers.ValidationError(
                "app can't change, create a new record"
            )
        if instance.s3bucket != validated_data['s3bucket']:
            raise serializers.ValidationError(
                "s3bucket can't change, create a new record"
            )

        return super().update(instance, validated_data)


class S3BucketSerializer(serializers.ModelSerializer):

    class Meta:
        model = S3Bucket
        fields = ('id', 'url', 'name', 'arn', 'apps3buckets')
