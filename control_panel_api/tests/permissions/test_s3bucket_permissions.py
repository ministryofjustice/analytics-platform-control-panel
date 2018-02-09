from unittest.mock import MagicMock, patch

from model_mommy import mommy
from rest_framework.reverse import reverse
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_201_CREATED,
    HTTP_204_NO_CONTENT,
    HTTP_403_FORBIDDEN,
    HTTP_404_NOT_FOUND,
)
from rest_framework.test import APITestCase

from control_panel_api.aws import aws


@patch.object(aws, 'client', MagicMock())
class S3BucketPermissionsTest(APITestCase):

    def setUp(self):
        super().setUp()

        self.superuser = mommy.make(
            'control_panel_api.User',
            is_superuser=True)
        self.normal_user = mommy.make(
            'control_panel_api.User',
            is_superuser=False)

        self.s3bucket_1 = mommy.make(
            "control_panel_api.S3Bucket",
            name="test-bucket-1")
        self.s3bucket_2 = mommy.make(
            "control_panel_api.S3Bucket",
            name="test-bucket-2")

        mommy.make(
            "control_panel_api.UserS3Bucket",
            user=self.normal_user,
            s3bucket=self.s3bucket_1)

    def test_list_as_superuser_responds_OK(self):
        self.client.force_login(self.superuser)

        response = self.client.get(reverse('s3bucket-list'))
        self.assertEqual(HTTP_200_OK, response.status_code)

    def test_list_as_normal_user_responds_OK(self):
        self.client.force_login(self.normal_user)

        response = self.client.get(reverse('s3bucket-list'))
        self.assertEqual(HTTP_200_OK, response.status_code)

    def test_detail_as_superuser_responds_OK(self):
        self.client.force_login(self.superuser)

        response = self.client.get(
            reverse('s3bucket-detail', (self.s3bucket_1.id,)))
        self.assertEqual(HTTP_200_OK, response.status_code)

    def test_detail_as_normal_user_responds_200_if_has_access(self):
        self.client.force_login(self.normal_user)

        response = self.client.get(
            reverse('s3bucket-detail', (self.s3bucket_1.id,)))
        self.assertEqual(HTTP_200_OK, response.status_code)

    def test_detail_as_normal_user_responds_404_if_has_not_access(self):
        self.client.force_login(self.normal_user)

        response = self.client.get(
            reverse('s3bucket-detail', (self.s3bucket_2.id,)))
        self.assertEqual(HTTP_404_NOT_FOUND, response.status_code)

    def test_delete_as_superuser_responds_OK(self):
        self.client.force_login(self.superuser)

        response = self.client.delete(
            reverse('s3bucket-detail', (self.s3bucket_1.id,)))
        self.assertEqual(HTTP_204_NO_CONTENT, response.status_code)

    def test_delete_as_normal_user_responds_403(self):
        self.client.force_login(self.normal_user)

        response = self.client.delete(
            reverse('s3bucket-detail', (self.s3bucket_1.id,)))
        self.assertEqual(HTTP_403_FORBIDDEN, response.status_code)

    def test_create_as_superuser_responds_OK(self):
        self.client.force_login(self.superuser)

        data = {'name': 'test-bucket'}
        response = self.client.post(reverse('s3bucket-list'), data)
        self.assertEqual(HTTP_201_CREATED, response.status_code)

    def test_create_as_normal_user_responds_OK(self):
        self.client.force_login(self.normal_user)

        data = {'name': 'test-bucket'}
        response = self.client.post(reverse('s3bucket-list'), data)
        self.assertEqual(HTTP_201_CREATED, response.status_code)

    def test_update_as_superuser_responds_OK(self):
        self.client.force_login(self.superuser)

        data = {'name': 'test-bucket-updated'}
        response = self.client.put(
            reverse('s3bucket-detail', (self.s3bucket_1.id,)), data)
        self.assertEqual(HTTP_200_OK, response.status_code)

    def test_update_as_normal_user_responds_403(self):
        self.client.force_login(self.normal_user)

        data = {'name': 'test-bucket-updated'}
        response = self.client.put(
            reverse('s3bucket-detail', (self.s3bucket_1.id,)), data)
        self.assertEqual(HTTP_403_FORBIDDEN, response.status_code)
