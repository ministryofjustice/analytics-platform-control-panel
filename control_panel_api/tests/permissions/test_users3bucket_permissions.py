from unittest.mock import MagicMock, patch

from model_mommy import mommy
from rest_framework.reverse import reverse
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_201_CREATED,
    HTTP_204_NO_CONTENT,
    HTTP_400_BAD_REQUEST,
    HTTP_403_FORBIDDEN,
)
from rest_framework.test import APITestCase

from control_panel_api.models import AccessToS3Bucket


@patch('control_panel_api.aws.aws.client', MagicMock())
class UserS3Buckets(APITestCase):
    def setUp(self):
        self.superuser = mommy.make(
            'control_panel_api.User',
            auth0_id='github|user_1',
            is_superuser=True,
        )
        self.normal_user = mommy.make(
            'control_panel_api.User',
            username='alice normal',
            auth0_id='github|user_2',
            is_superuser=False,
        )

        self.user_1 = mommy.make("control_panel_api.User", is_superuser=False)

        self.s3bucket_1 = mommy.make("control_panel_api.S3Bucket")
        self.s3bucket_2 = mommy.make("control_panel_api.S3Bucket")

        self.normal_user_admin = mommy.make(
            "control_panel_api.UserS3Bucket",
            user=self.normal_user,
            s3bucket=self.s3bucket_1,
            access_level=AccessToS3Bucket.READWRITE,
            is_admin=True,
        )
        self.normal_user_other_bucket_non_admin = mommy.make(
            "control_panel_api.UserS3Bucket",
            user=self.normal_user,
            s3bucket=self.s3bucket_2,
            access_level=AccessToS3Bucket.READWRITE,
            is_admin=False,
        )
        self.other_user_normal_user_has_admin = mommy.make(
            "control_panel_api.UserS3Bucket",
            user=self.user_1,
            s3bucket=self.s3bucket_1,
            access_level=AccessToS3Bucket.READWRITE,
            is_admin=True,
        )

    def test_create_superuser_ok(self):
        self.client.force_login(self.superuser)

        data = {
            'user': self.user_1.auth0_id,
            's3bucket': self.s3bucket_2.id,
            'access_level': AccessToS3Bucket.READWRITE,
        }
        response = self.client.post(reverse('users3bucket-list'), data)
        self.assertEqual(HTTP_201_CREATED, response.status_code)

    def test_create_normal_user_bad_data_400(self):
        self.client.force_login(self.normal_user)

        data = {'doesnt': 'matter'}
        response = self.client.post(reverse('users3bucket-list'), data)
        self.assertEqual(HTTP_400_BAD_REQUEST, response.status_code)

    def test_create_normal_user_other_admin_ok(self):
        self.client.force_login(self.normal_user)

        data = {
            'user': mommy.make('control_panel_api.User').auth0_id,
            's3bucket': self.s3bucket_1.id,
            'access_level': AccessToS3Bucket.READWRITE,
            'is_admin': True,
        }
        response = self.client.post(reverse('users3bucket-list'), data)
        self.assertEqual(HTTP_201_CREATED, response.status_code)

    def test_create_normal_user_non_admin_403(self):
        self.client.force_login(self.normal_user)

        data = {
            'user': mommy.make('control_panel_api.User').auth0_id,
            's3bucket': self.s3bucket_2.id,
            'access_level': AccessToS3Bucket.READWRITE,
            'is_admin': True,
        }
        response = self.client.post(reverse('users3bucket-list'), data)
        self.assertEqual(HTTP_403_FORBIDDEN, response.status_code)

    def test_delete_super_user_owner_admin_ok(self):
        self.client.force_login(self.superuser)

        response = self.client.delete(
            reverse('users3bucket-detail', (self.normal_user_admin.id,)))
        self.assertEqual(HTTP_204_NO_CONTENT, response.status_code)

    def test_delete_normal_user_owner_admin_ok(self):
        self.client.force_login(self.normal_user)

        response = self.client.delete(
            reverse('users3bucket-detail', (self.normal_user_admin.id,)))
        self.assertEqual(HTTP_204_NO_CONTENT, response.status_code)

    def test_delete_normal_user_other_admin_ok(self):
        self.client.force_login(self.normal_user)

        response = self.client.delete(
            reverse('users3bucket-detail',
                    (self.other_user_normal_user_has_admin.id,)))
        self.assertEqual(HTTP_204_NO_CONTENT, response.status_code)

    def test_delete_normal_user_owner_non_admin_403(self):
        self.client.force_login(self.normal_user)

        response = self.client.delete(
            reverse('users3bucket-detail',
                    (self.normal_user_other_bucket_non_admin.id,)))
        self.assertEqual(HTTP_403_FORBIDDEN, response.status_code)

    def test_update(self):
        fixtures = [
            {
                'user': self.superuser,
                'users3bucket': self.normal_user_admin,
                'expected_code': HTTP_200_OK,
            },
            {
                'user': self.normal_user,
                'users3bucket': self.normal_user_admin,
                'expected_code': HTTP_200_OK,
            },
            {
                'user': self.normal_user,
                'users3bucket': self.other_user_normal_user_has_admin,
                'expected_code': HTTP_200_OK,
            },
            {
                'user': self.normal_user,
                'users3bucket': self.normal_user_other_bucket_non_admin,
                'expected_code': HTTP_403_FORBIDDEN,
            },
        ]

        for fixture in fixtures:
            self.client.force_login(fixture['user'])

            response = self.client.patch(
                reverse('users3bucket-detail', (fixture['users3bucket'].id,)),
                {'access_level': AccessToS3Bucket.READONLY}
            )
            self.assertEqual(fixture['expected_code'], response.status_code)
