from model_mommy import mommy
from rest_framework.reverse import reverse
from rest_framework.status import HTTP_403_FORBIDDEN
from rest_framework.test import APITestCase

from controlpanel.api.models import AppS3Bucket


class AppS3BucketFilterTest(APITestCase):

    def setUp(self):
        # Create users
        self.superuser = mommy.make(
            "api.User", is_superuser=True)
        self.normal_user = mommy.make(
            "api.User", is_superuser=False)
        # Create some apps
        self.app_1 = mommy.make(
            "api.App", name="App 1")
        self.app_2 = mommy.make(
            "api.App", name="App 2")
        # Create some S3 buckets
        self.s3bucket_1 = mommy.make(
            "api.S3Bucket", name="test-bucket-1")
        self.s3bucket_2 = mommy.make(
            "api.S3Bucket", name="test-bucket-2")
        # Grant access to these S3 buckets
        self.apps3bucket_1 = self.app_1.apps3buckets.create(
            s3bucket=self.s3bucket_1,
            access_level=AppS3Bucket.READONLY,
        )
        self.apps3bucket_2 = self.app_2.apps3buckets.create(
            s3bucket=self.s3bucket_2,
            access_level=AppS3Bucket.READONLY,
        )

    def test_superuser_sees_everything(self):
        self.client.force_login(self.superuser)

        response = self.client.get(reverse("apps3bucket-list"))
        ids = [apps3bucket["id"] for apps3bucket in response.data["results"]]

        self.assertEqual(len(ids), 2)
        self.assertIn(self.apps3bucket_1.id, ids)
        self.assertIn(self.apps3bucket_2.id, ids)

    def test_normal_user_sees_nothing(self):
        self.client.force_login(self.normal_user)

        response = self.client.get(reverse("apps3bucket-list"))
        self.assertEqual(HTTP_403_FORBIDDEN, response.status_code)

