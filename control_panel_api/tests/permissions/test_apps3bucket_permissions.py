from unittest.mock import MagicMock, patch

from model_mommy import mommy
from rest_framework.reverse import reverse
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_201_CREATED,
    HTTP_204_NO_CONTENT,
    HTTP_403_FORBIDDEN,
)
from rest_framework.test import APITestCase

from control_panel_api.models import AppS3Bucket


@patch('control_panel_api.aws.aws.client', MagicMock())
class AppS3BucketPermissionsTest(APITestCase):
    def setUp(self):
        super().setUp()
        self.superuser = mommy.make(
            "control_panel_api.User", is_superuser=True)
        self.normal_user = mommy.make(
            "control_panel_api.User", is_superuser=False)

        self.app_1 = mommy.make(
            "control_panel_api.App", name="App 1")
        self.app_2 = mommy.make(
            "control_panel_api.App", name="App 2")

        self.s3bucket_1 = mommy.make(
            "control_panel_api.S3Bucket", name="test-bucket-1")
        self.s3bucket_2 = mommy.make(
            "control_panel_api.S3Bucket", name="test-bucket-2")
        self.s3bucket_3 = mommy.make(
            "control_panel_api.S3Bucket", name="test-bucket-3")

        self.apps3bucket_1 = self.app_1.apps3buckets.create(
            s3bucket=self.s3bucket_1,
            access_level=AppS3Bucket.READONLY,
        )
        self.apps3bucket_2 = self.app_2.apps3buckets.create(
            s3bucket=self.s3bucket_2,
            access_level=AppS3Bucket.READONLY,
        )

    def test_list_as_superuser_responds_OK(self):
        self.client.force_login(self.superuser)

        response = self.client.get(reverse('apps3bucket-list'))
        self.assertEqual(HTTP_200_OK, response.status_code)

    def test_list_as_normal_user_responds_403(self):
        self.client.force_login(self.normal_user)

        response = self.client.get(reverse('apps3bucket-list'))
        self.assertEqual(HTTP_403_FORBIDDEN, response.status_code)

    def test_detail_as_superuser_responds_OK(self):
        self.client.force_login(self.superuser)

        response = self.client.get(
            reverse('apps3bucket-detail', (self.apps3bucket_1.id,)))
        self.assertEqual(HTTP_200_OK, response.status_code)

    def test_detail_as_normal_user_responds_403(self):
        self.client.force_login(self.normal_user)

        response = self.client.get(
            reverse('apps3bucket-detail', (self.apps3bucket_1.id,)))
        self.assertEqual(HTTP_403_FORBIDDEN, response.status_code)

    def test_delete_as_superuser_responds_OK(self):
        self.client.force_login(self.superuser)

        response = self.client.delete(
            reverse('apps3bucket-detail', (self.apps3bucket_1.id,)))
        self.assertEqual(HTTP_204_NO_CONTENT, response.status_code)

    def test_delete_as_normal_user_responds_403(self):
        self.client.force_login(self.normal_user)

        response = self.client.delete(
            reverse('apps3bucket-detail', (self.apps3bucket_1.id,)))
        self.assertEqual(HTTP_403_FORBIDDEN, response.status_code)

    def test_create_as_superuser_responds_OK(self):
        self.client.force_login(self.superuser)

        data = {
            'app': self.app_1.id,
            's3bucket': self.s3bucket_3.id,
            'access_level': AppS3Bucket.READWRITE,
        }
        response = self.client.post(reverse('apps3bucket-list'), data)
        self.assertEqual(HTTP_201_CREATED, response.status_code)

    def test_create_as_normal_user_responds_403(self):
        self.client.force_login(self.normal_user)

        data = {'doesnt': 'matter'}
        response = self.client.post(reverse('apps3bucket-list'), data)
        self.assertEqual(HTTP_403_FORBIDDEN, response.status_code)

    def test_update_as_superuser_responds_OK(self):
        self.client.force_login(self.superuser)

        data = {
            'app': self.app_1.id,
            's3bucket': self.s3bucket_1.id,
            'access_level': AppS3Bucket.READWRITE,
        }
        response = self.client.put(
            reverse('apps3bucket-detail', (self.apps3bucket_1.id,)), data)
        self.assertEqual(HTTP_200_OK, response.status_code)

    def test_update_as_normal_user_responds_403(self):
        self.client.force_login(self.normal_user)

        data = {'doesnt': 'matter'}
        response = self.client.put(
            reverse('apps3bucket-detail', (self.apps3bucket_1.id,)), data)
        self.assertEqual(HTTP_403_FORBIDDEN, response.status_code)
