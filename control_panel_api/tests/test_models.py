from unittest.mock import MagicMock, patch

from django.db.utils import IntegrityError
from django.test import TestCase
from model_mommy import mommy

from control_panel_api.models import (
    App,
    AppS3Bucket,
    S3Bucket,
    TeamMembership,
    User,
    UserS3Bucket,
)
from control_panel_api.tests import APP_IAM_ROLE_ASSUME_POLICY


@patch('control_panel_api.helm.subprocess.run', MagicMock())
class UserTestCase(TestCase):
    @patch('control_panel_api.helm.init_user')
    @patch('control_panel_api.helm.config_user')
    def test_helm_create_user(self, mock_config_user, mock_init_user):
        username = 'foo'
        email = 'bar@baz.com'
        name = 'bat'
        user = User.objects.create(
            username=username,
            email=email,
            name=name,
        )
        user.helm_create()

        mock_config_user.assert_called_with(username)
        mock_init_user.assert_called_with(username, email, name)

    @patch('control_panel_api.services.create_role')
    def test_aws_create_role_calls_service(self, mock_create_role):
        username = 'james'
        user = User.objects.create(username=username)
        user.aws_create_role()

        expected_role_name = f"test_user_{username}"

        mock_create_role.assert_called_with(
            expected_role_name,
            add_saml_statement=True
        )

    @patch('control_panel_api.services.delete_role')
    def test_aws_delete_role_calls_service(self, mock_delete_role):
        username = 'james'
        user = User.objects.create(username=username)
        user.aws_delete_role()

        expected_role_name = f"test_user_{username}"

        mock_delete_role.assert_called_with(expected_role_name)


class MembershipsTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user_alice, cls.user_bob, cls.user_other = mommy.make(
            'control_panel_api.User', _quantity=3)

        cls.team_justice, cls.team_other = mommy.make(
            'control_panel_api.Team', _quantity=2)

        cls.role_maintainer = mommy.make(
            'control_panel_api.Role', code="maintainer", name="Maintainer")

        cls.role_member = mommy.make(
            'control_panel_api.Role', code="member", name="Member")

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
        repo_url = 'https://example.com/foo__bar-baz!bat-1337'

        app = App.objects.create(repo_url=repo_url)
        self.assertEqual('foo-bar-bazbat-1337', app.slug)

    def test_slug_collisions_increments(self):
        app = App.objects.create(
            repo_url='git@github.com:org/foo-bar.git',
        )
        self.assertEqual('foo-bar', app.slug)

        app2 = App.objects.create(
            repo_url='https://www.example.com/org/foo-bar',
        )
        self.assertEqual('foo-bar-2', app2.slug)

    @patch('control_panel_api.aws.create_role')
    def test_aws_create_role_calls_service(self, mock_create_role):
        app = App.objects.create(repo_url='https://example.com/repo_name')
        app.aws_create_role()

        expected_role_name = f"test_app_{app.slug}"

        mock_create_role.assert_called_with(
            expected_role_name,
            APP_IAM_ROLE_ASSUME_POLICY
        )

    @patch('control_panel_api.aws.delete_role')
    def test_aws_delete_role_calls_service(self, mock_delete_role):
        app = App.objects.create(repo_url='https://example.com/repo_name')
        app.aws_delete_role()

        expected_role_name = f"test_app_{app.slug}"

        mock_delete_role.assert_called_with(expected_role_name)


class S3BucketTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Create an S3 bucket
        cls.s3_bucket_1 = S3Bucket.objects.create(name="test-bucket-1")

    def test_arn(self):
        self.assertEqual(
            'arn:aws:s3:::test-bucket-1',
            self.s3_bucket_1.arn
        )

    @patch('control_panel_api.services.create_bucket')
    @patch('control_panel_api.services.create_bucket_policies')
    def test_bucket_create(self, mock_create_bucket_policies,
                           mock_create_bucket):
        self.s3_bucket_1.aws_create()

        mock_create_bucket_policies.assert_called()
        mock_create_bucket.assert_called()

    @patch('control_panel_api.services.delete_bucket_policies')
    def test_bucket_delete(self, mock_delete_bucket_policies):
        self.s3_bucket_1.aws_delete()

        mock_delete_bucket_policies.assert_called()


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

    @patch('control_panel_api.services.update_bucket_access')
    def test_update_aws_permissions(self, mock_apps3bucket_update):
        apps3bucket = AppS3Bucket.objects.create(
            app=self.app_1,
            s3bucket=self.s3_bucket_1,
            access_level=AppS3Bucket.READONLY,
        )

        apps3bucket.aws_update()

        mock_apps3bucket_update.assert_called_with(
            self.s3_bucket_1.name,
            apps3bucket.has_readwrite_access(),
            self.app_1.iam_role_name
        )

    @patch('control_panel_api.services.attach_bucket_access_to_role')
    def test_aws_create(self, mock_attach_bucket_access_to_role):
        apps3bucket = self.app_1.apps3buckets.create(
            s3bucket=self.s3_bucket_1,
            access_level=AppS3Bucket.READONLY,
        )

        apps3bucket.aws_create()

        mock_attach_bucket_access_to_role.assert_called_with(
            self.s3_bucket_1.name,
            apps3bucket.has_readwrite_access(),
            self.app_1.iam_role_name
        )

    @patch('control_panel_api.services.detach_bucket_access_from_role')
    def test_aws_delete(self, mock_detach_bucket_access_from_app_role):
        apps3bucket = self.app_1.apps3buckets.create(
            s3bucket=self.s3_bucket_1,
            access_level=AppS3Bucket.READONLY,
        )

        apps3bucket.aws_delete()

        mock_detach_bucket_access_from_app_role.assert_called_with(
            self.s3_bucket_1.name,
            apps3bucket.has_readwrite_access(),
            self.app_1.iam_role_name
        )


class UserS3BucketTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.user_1 = User.objects.create(auth0_id='github|user_1',
                                         username="user_1")
        cls.user_2 = User.objects.create(auth0_id='github|user_2',
                                         username="user_2")

        cls.s3_bucket_1 = S3Bucket.objects.create(name="test-bucket-1")

        cls.users3bucket_1 = cls.user_1.users3buckets.create(
            s3bucket=cls.s3_bucket_1,
            access_level=AppS3Bucket.READONLY,
        )

    def test_one_record_per_user_per_s3bucket(self):
        with self.assertRaises(IntegrityError):
            self.user_1.users3buckets.create(
                s3bucket=self.s3_bucket_1,
                access_level=UserS3Bucket.READWRITE,
            )

    @patch('control_panel_api.services.attach_bucket_access_to_role')
    def test_aws_create(self, mock_attach_bucket_access_to_app_role):
        self.users3bucket_1.aws_create()

        mock_attach_bucket_access_to_app_role.assert_called_with(
            self.s3_bucket_1.name,
            self.users3bucket_1.has_readwrite_access(),
            self.user_1.iam_role_name,
        )

    @patch('control_panel_api.services.detach_bucket_access_from_role')
    def test_aws_delete(self, mock_detach_bucket_access_from_app_role):
        self.users3bucket_1.aws_delete()

        mock_detach_bucket_access_from_app_role.assert_called_with(
            self.s3_bucket_1.name,
            self.users3bucket_1.has_readwrite_access(),
            self.user_1.iam_role_name
        )
