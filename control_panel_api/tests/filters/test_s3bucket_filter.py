from model_mommy import mommy
from rest_framework.reverse import reverse
from rest_framework.status import HTTP_403_FORBIDDEN
from rest_framework.test import APITestCase


class S3BucketFilterTest(APITestCase):

    def setUp(self):
        # Create users
        self.superuser = mommy.make(
            "control_panel_api.User", is_superuser=True)
        self.normal_user = mommy.make(
            "control_panel_api.User", is_superuser=False)
        # Create some S3 buckets
        self.s3_bucket_1 = mommy.make(
            "control_panel_api.S3Bucket", name="test-bucket-1")
        self.s3_bucket_2 = mommy.make(
            "control_panel_api.S3Bucket", name="test-bucket-2")

    def test_superuser_sees_everything(self):
        self.client.force_login(self.superuser)

        response = self.client.get(reverse("s3bucket-list"))
        s3_bucket_ids = [s3bucket["id"]
                         for s3bucket in response.data["results"]]
        self.assertEqual(len(s3_bucket_ids), 2)
        self.assertIn(self.s3_bucket_1.id, s3_bucket_ids)
        self.assertIn(self.s3_bucket_2.id, s3_bucket_ids)

    def test_normal_user_sees_nothing(self):
        self.client.force_login(self.normal_user)

        response = self.client.get(reverse("s3bucket-list"))
        self.assertEqual(HTTP_403_FORBIDDEN, response.status_code)
