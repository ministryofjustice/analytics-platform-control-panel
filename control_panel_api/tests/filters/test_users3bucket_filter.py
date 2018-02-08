from model_mommy import mommy
from rest_framework.reverse import reverse
from rest_framework.status import HTTP_200_OK
from rest_framework.test import APITestCase

from control_panel_api.models import UserS3Bucket


class UserS3BucketFilterTest(APITestCase):

    def setUp(self):
        # Create users
        self.superuser = mommy.make(
            "control_panel_api.User", is_superuser=True)
        self.normal_user = mommy.make(
            "control_panel_api.User", is_superuser=False)
        self.normal_user_2 = mommy.make(
            "control_panel_api.User", is_superuser=False)
        # Create some S3 buckets
        self.s3bucket_1 = mommy.make(
            "control_panel_api.S3Bucket", name="test-bucket-1")
        self.s3bucket_2 = mommy.make(
            "control_panel_api.S3Bucket", name="test-bucket-2")
        # Grant access to these S3 buckets
        self.s3bucket_1_normal_user_access = self.normal_user.users3buckets.create(
            s3bucket=self.s3bucket_1,
            access_level=UserS3Bucket.READONLY,
        )
        self.s3bucket_1_normal_user_2_access = self.normal_user_2.users3buckets.create(
            s3bucket=self.s3bucket_1,
            access_level=UserS3Bucket.READONLY,
        )
        self.s3bucket_2_superuser_access = self.superuser.users3buckets.create(
            s3bucket=self.s3bucket_2,
            access_level=UserS3Bucket.READWRITE,
        )

    def test_superuser_sees_everything(self):
        self.client.force_login(self.superuser)

        response = self.client.get(reverse("users3bucket-list"))
        ids = [us["id"] for us in response.data["results"]]

        self.assertEqual(HTTP_200_OK, response.status_code)
        self.assertEqual(len(ids), 3)
        self.assertIn(self.s3bucket_1_normal_user_access.id, ids)
        self.assertIn(self.s3bucket_1_normal_user_2_access.id, ids)
        self.assertIn(self.s3bucket_2_superuser_access.id, ids)

    def test_normal_user_only_sees_records_for_buckets_has_access_to(self):
        """
        NOTE: As per requirements, user can see all the `UserS3Bucket` records
              for buckets he has access to. Basically can see which other
              users have access to buckets he can read or write.
        """

        self.client.force_login(self.normal_user)

        response = self.client.get(reverse("users3bucket-list"))
        self.assertEqual(HTTP_200_OK, response.status_code)

        ids = [us["id"] for us in response.data["results"]]
        self.assertIn(self.s3bucket_1_normal_user_access.id, ids)
        self.assertIn(self.s3bucket_1_normal_user_2_access.id, ids)
        self.assertNotIn(self.s3bucket_2_superuser_access.id, ids)
