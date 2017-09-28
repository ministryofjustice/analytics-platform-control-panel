from unittest.mock import patch

from django.db.utils import IntegrityError
from django.test import TestCase, TransactionTestCase

from control_panel_api.models import (
    App,
    AppS3Bucket,
    Role,
    S3Bucket,
    Team,
    TeamMembership,
    User,
    UserS3Bucket,
)


class MembershipsTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        # Users
        cls.user_alice, _ = User.objects.get_or_create(username="Alice")
        cls.user_bob, _ = User.objects.get_or_create(username="Bob")
        cls.user_other, _ = User.objects.get_or_create(username="Other")
        # Teams
        cls.team_justice, _ = Team.objects.get_or_create(name="Justice Team")
        cls.team_other, _ = Team.objects.get_or_create(name="Other Team")
        # Roles
        cls.role_maintainer, _ = Role.objects.get_or_create(
            code="maintainer",
            name="Maintainer",
        )
        cls.role_member, _ = Role.objects.get_or_create(
            code="member",
            name="Member",
        )

        # Add Alice to Justice team as maintainer
        TeamMembership.objects.create(
            team=cls.team_justice,
            user=cls.user_alice,
            role=cls.role_maintainer,
        )
        # Add Bob to Justice team as member
        TeamMembership.objects.create(
            team=cls.team_justice,
            user=cls.user_bob,
            role=cls.role_member,
        )
        # Add other user to other team as member
        TeamMembership.objects.create(
            team=cls.team_other,
            user=cls.user_other,
            role=cls.role_member,
        )

    def test_get_user_teams(self):
        alices_teams = self.user_alice.teams.all()

        self.assertIn(self.team_justice, alices_teams)
        self.assertNotIn(self.team_other, alices_teams)

    def test_get_users_in_a_team(self):
        justice_users = self.team_justice.users.all()

        self.assertIn(self.user_alice, justice_users)
        self.assertIn(self.user_bob, justice_users)
        self.assertNotIn(self.user_other, justice_users)

    def test_get_users_with_a_role_in_team(self):
        justice_maintainers = self.team_justice.users_with_role("maintainer")
        justice_members = self.team_justice.users_with_role("member")

        self.assertIn(self.user_alice, justice_maintainers)
        self.assertNotIn(self.user_alice, justice_members)
        self.assertNotIn(self.user_bob, justice_maintainers)
        self.assertIn(self.user_bob, justice_members)
        self.assertNotIn(self.user_other, justice_maintainers)
        self.assertNotIn(self.user_other, justice_members)

    def test_user_can_be_added_to_team_only_once(self):
        with self.assertRaises(IntegrityError):
            # (trying to) Add Alice to team justice again
            TeamMembership.objects.create(
                team=self.team_justice,
                user=self.user_alice,
                role=self.role_member,
            )


class AppTestCase(TestCase):

    def test_slug_characters_replaced(self):
        name = 'foo__bar-baz!bat 1337'

        app = App.objects.create(name=name)
        self.assertEqual('foo-bar-bazbat-1337', app.slug)

    def test_slug_collisions_increments(self):
        name = 'foo'

        app = App.objects.create(name=name)
        self.assertEqual('foo', app.slug)

        app2 = App.objects.create(name=name)
        self.assertEqual('foo-2', app2.slug)


class S3BucketTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        # Create an S3 bucket
        cls.s3_bucket_1 = S3Bucket.objects.create(name="test-bucket-1")

    def test_arn(self):
        expected_arn = "arn:aws:s3:::{}".format(self.s3_bucket_1.name)

        self.assertEqual(self.s3_bucket_1.arn, expected_arn)


class AppS3BucketTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        # Apps
        cls.app_1 = App.objects.create(name="app_1")

        # S3 buckets
        cls.s3_bucket_1 = S3Bucket.objects.create(name="test-bucket-1")

    def test_one_record_per_app_per_s3bucket(self):
        # Give app_1 access to bucket_1 (read-only)
        self.app_1.apps3buckets.create(
            s3bucket=self.s3_bucket_1,
            access_level=AppS3Bucket.READONLY,
        )

        with self.assertRaises(IntegrityError):
            self.app_1.apps3buckets.create(
                s3bucket=self.s3_bucket_1,
                access_level=AppS3Bucket.READWRITE,
            )

    @patch('control_panel_api.services.apps3bucket_update')
    def test_update_aws_permissions(self, mock_apps3bucket_update):
        apps3bucket = AppS3Bucket.objects.create(
            app=self.app_1,
            s3bucket=self.s3_bucket_1,
            access_level=AppS3Bucket.READONLY,
        )
        apps3bucket.update_aws_permissions()
        mock_apps3bucket_update.assert_called_with(apps3bucket)



class UserS3BucketTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        # Users
        cls.user_1 = User.objects.create(username="user_1")

        # S3 buckets
        cls.s3_bucket_1 = S3Bucket.objects.create(name="test-bucket-1")

    def test_one_record_per_user_per_s3bucket(self):
        # Give user_1 access to bucket_1 (read-only)
        self.user_1.users3buckets.create(
            s3bucket=self.s3_bucket_1,
            access_level=UserS3Bucket.READONLY,
        )

        with self.assertRaises(IntegrityError):
            self.user_1.users3buckets.create(
                s3bucket=self.s3_bucket_1,
                access_level=UserS3Bucket.READWRITE,
            )
