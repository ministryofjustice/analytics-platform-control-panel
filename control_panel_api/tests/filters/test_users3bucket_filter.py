from model_mommy import mommy
from rest_framework.reverse import reverse
from rest_framework.status import HTTP_403_FORBIDDEN
from rest_framework.test import APITestCase

from control_panel_api.models import UserS3Bucket


class UserS3BucketFilterTest(APITestCase):

    def setUp(self):
        # Create users
        self.superuser = mommy.make(
            "control_panel_api.User", is_superuser=True)
        self.normal_user = mommy.make(
            "control_panel_api.User", is_superuser=False)
        # Create some S3 buckets
        self.s3bucket_1 = mommy.make(
            "control_panel_api.S3Bucket", name="test-bucket-1")
        self.s3bucket_2 = mommy.make(
            "control_panel_api.S3Bucket", name="test-bucket-2")
        # Grant access to these S3 buckets
        self.users3bucket_1 = self.normal_user.users3buckets.create(
            s3bucket=self.s3bucket_1,
            access_level=UserS3Bucket.READONLY,
        )
        self.users3bucket_2 = self.superuser.users3buckets.create(
            s3bucket=self.s3bucket_2,
            access_level=UserS3Bucket.READWRITE,
        )

    def test_superuser_sees_everything(self):
        self.client.force_login(self.superuser)

        response = self.client.get(reverse("users3bucket-list"))
        ids = [us["id"] for us in response.data["results"]]

        self.assertEqual(len(ids), 2)
        self.assertIn(self.users3bucket_1.id, ids)
        self.assertIn(self.users3bucket_2.id, ids)

    def test_normal_user_sees_nothing(self):
        self.client.force_login(self.normal_user)

        response = self.client.get(reverse("users3bucket-list"))
        self.assertEqual(HTTP_403_FORBIDDEN, response.status_code)
