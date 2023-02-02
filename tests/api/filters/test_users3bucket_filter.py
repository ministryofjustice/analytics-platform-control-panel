# Third-party
from model_mommy import mommy
from rest_framework.reverse import reverse
from rest_framework.status import HTTP_200_OK
from rest_framework.test import APITestCase

# First-party/Local
from controlpanel.api.models import UserS3Bucket


class UserS3BucketFilterTest(APITestCase):
    def setUp(self):
        self.superuser = mommy.make("api.User", is_superuser=True)
        self.normal_user = mommy.make("api.User", is_superuser=False)
        self.other_user = mommy.make("api.User", is_superuser=False)

        self.s3bucket_1 = mommy.make("api.S3Bucket", name="test-bucket-1")
        self.s3bucket_2 = mommy.make("api.S3Bucket", name="test-bucket-2")
        self.s3bucket_3 = mommy.make("api.S3Bucket", name="test-bucket-3")

        self.s3bucket_1_normal_user_access = mommy.make(
            "api.UserS3Bucket",
            user=self.normal_user,
            s3bucket=self.s3bucket_1,
            access_level=UserS3Bucket.READONLY,
        )
        self.s3bucket_1_other_user_access = mommy.make(
            "api.UserS3Bucket",
            user=self.other_user,
            s3bucket=self.s3bucket_1,
            access_level=UserS3Bucket.READONLY,
        )
        self.s3bucket_2_normal_user_access = mommy.make(
            "api.UserS3Bucket",
            user=self.normal_user,
            s3bucket=self.s3bucket_2,
            access_level=UserS3Bucket.READONLY,
        )
        self.s3bucket_2_superuser_access = mommy.make(
            "api.UserS3Bucket",
            user=self.superuser,
            s3bucket=self.s3bucket_2,
            access_level=UserS3Bucket.READWRITE,
        )
        self.s3bucket_3_superuser_access = mommy.make(
            "api.UserS3Bucket",
            user=self.superuser,
            s3bucket=self.s3bucket_3,
            access_level=UserS3Bucket.READWRITE,
        )

    def test_superuser_sees_everything(self):
        self.client.force_login(self.superuser)

        response = self.client.get(reverse("users3bucket-list"))
        ids = [us["id"] for us in response.data["results"]]

        self.assertEqual(HTTP_200_OK, response.status_code)
        self.assertEqual(len(ids), 5)
        self.assertIn(self.s3bucket_1_normal_user_access.id, ids)
        self.assertIn(self.s3bucket_1_other_user_access.id, ids)
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

        ids = [result["id"] for result in response.data["results"]]
        self.assertIn(self.s3bucket_1_normal_user_access.id, ids)
        self.assertIn(self.s3bucket_1_other_user_access.id, ids)
        self.assertIn(self.s3bucket_2_normal_user_access.id, ids)
        self.assertIn(self.s3bucket_2_superuser_access.id, ids)
        self.assertNotIn(self.s3bucket_3_superuser_access.id, ids)
