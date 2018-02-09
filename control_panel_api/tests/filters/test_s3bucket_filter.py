from model_mommy import mommy
from rest_framework.reverse import reverse
from rest_framework.status import HTTP_200_OK
from rest_framework.test import APITestCase


class S3BucketFilterTest(APITestCase):

    def setUp(self):
        self.superuser = mommy.make("control_panel_api.User",
                                    is_superuser=True)
        self.normal_user = mommy.make("control_panel_api.User",
                                      is_superuser=False)

        self.s3_bucket_1 = mommy.make("control_panel_api.S3Bucket",
                                      name="test-bucket-1")
        self.s3_bucket_2 = mommy.make("control_panel_api.S3Bucket",
                                      name="test-bucket-2")

        mommy.make("control_panel_api.UserS3Bucket",
                   user=self.normal_user,
                   s3bucket=self.s3_bucket_1,
                   access_level='readonly',
                   is_admin=False)

    def test_superuser_sees_everything(self):
        self.client.force_login(self.superuser)

        response = self.client.get(reverse("s3bucket-list"))
        s3_bucket_ids = [b["id"] for b in response.data["results"]]
        self.assertEqual(len(s3_bucket_ids), 2)
        self.assertIn(self.s3_bucket_1.id, s3_bucket_ids)
        self.assertIn(self.s3_bucket_2.id, s3_bucket_ids)

    def test_normal_user_sees_only_buckets_has_access_to(self):
        self.client.force_login(self.normal_user)

        response = self.client.get(reverse("s3bucket-list"))
        self.assertEqual(HTTP_200_OK, response.status_code)

        s3_bucket_ids = [b["id"] for b in response.data["results"]]
        self.assertIn(self.s3_bucket_1.id, s3_bucket_ids)
        self.assertNotIn(self.s3_bucket_2.id, s3_bucket_ids)
