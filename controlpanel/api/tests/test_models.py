import json
from operator import itemgetter
from unittest.mock import MagicMock, call, patch

from django.conf import settings
from django.db.utils import IntegrityError
from django.test import TestCase
from model_mommy import mommy

from control_panel_api.auth0 import User as Auth0User
from control_panel_api.aws import aws
from control_panel_api.helm import helm
from control_panel_api.models import (
    App,
    AppS3Bucket,
    S3Bucket,
    TeamMembership,
    User,
    UserS3Bucket,
)
from control_panel_api.tests import (
    APP_IAM_ROLE_ASSUME_POLICY,
    USER_IAM_ROLE_ASSUME_POLICY,
)


@patch.object(aws, 'client', MagicMock())
@patch.object(helm, 'config_user', MagicMock())
@patch.object(helm, 'init_user', MagicMock())
@patch.object(helm, 'uninstall_user_charts', MagicMock())
@patch.object(helm, 'uninstall_init_user_chart', MagicMock())
class UserTestCase(TestCase):

    def test_helm_create_user(self):
        user = mommy.prepare('control_panel_api.User')

        user.helm_create()

        helm.config_user.assert_called_with(user.username)
        helm.init_user.assert_called_with(user.username, user.email, user.name)

    def test_helm_delete_user(self):
        user = mommy.prepare('control_panel_api.User')

        user.helm_delete()

        helm.uninstall_user_charts.assert_called_with(user.username)
        helm.uninstall_init_user_chart.assert_called_with(user.username)

    def test_aws_create_role_calls_service(self):
        username = 'james'
        auth0_id = 'github|user_1'
        user = User.objects.create(auth0_id=auth0_id, username=username)
        user.aws_create_role()
        expected_role_name = f'test_user_{username}'

        aws_client = aws.client.return_value
        aws_client.create_role.assert_called_with(
            RoleName=expected_role_name,
            AssumeRolePolicyDocument=json.dumps(USER_IAM_ROLE_ASSUME_POLICY))
        aws_client.attach_role_policy.assert_called_with(
            RoleName=expected_role_name,
            PolicyArn=(
                f'{settings.IAM_ARN_BASE}:policy/'
                f'{settings.ENV}-read-user-roles-inline-policies'
            ),
        )

    def test_aws_delete_role_calls_service(self):
        username = 'james'
        user = User.objects.create(username=username)
        user.aws_delete_role()

        expected_role_name = f"test_user_{username}"

        aws.client.return_value.delete_role.assert_called_with(
            RoleName=expected_role_name)

    def test_k8s_namespace(self):
        user = User(username='AlicE')
        expected_ns = f'user-alice'

        self.assertEqual(user.k8s_namespace, expected_ns)


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


@patch.object(aws, 'client', MagicMock())
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

    def test_aws_create_role_calls_service(self):
        app = App.objects.create(repo_url='https://example.com/repo_name')
        app.aws_create_role()

        expected_role_name = f"test_app_{app.slug}"

        aws.client.return_value.create_role.assert_called_with(
            RoleName=expected_role_name,
            AssumeRolePolicyDocument=json.dumps(APP_IAM_ROLE_ASSUME_POLICY))

    def test_aws_delete_role_calls_service(self):
        app = App.objects.create(repo_url='https://example.com/repo_name')
        app.aws_delete_role()

        expected_role_name = f"test_app_{app.slug}"

        aws.client.return_value.delete_role.assert_called_with(
            RoleName=expected_role_name)

    @patch('control_panel_api.auth0.Auth0Client')
    def test_get_customers(self, auth0):
        auth0.return_value.authorization.get.return_value.get_members.return_value = [
            {'email': 'test@example.com'}
        ]

        app = App.objects.create(repo_url='https://example.com/repo_name')
        customers = app.get_customers()

        expected_customer_emails = ['test@example.com']

        self.assertEqual(
            expected_customer_emails,
            list(map(itemgetter('email'), customers)))

    @patch('control_panel_api.auth0.Auth0Client')
    def test_add_customers(self, mock_auth0_client):
        app = App.objects.create(repo_url='https://example.com/repo_name')
        auth0 = mock_auth0_client.return_value
        authz = auth0.authorization
        mgmt = auth0.management
        group = authz.get.return_value
        emails = [
            'test1@example.com',
            'test2@example.com'
        ]

        def mock_create_user(user):
            return Auth0User(user, user_id=emails.index(user['email']))

        mgmt.create.side_effect = mock_create_user

        def new_user(email):
            return Auth0User(
                email=email,
                email_verified=True,
                connection='email')

        def existing_user(email):
            return Auth0User(new_user(email), user_id=emails.index(email))

        def assert_case(all_users, expected_created, expected_added):
            authz.get_all.return_value = all_users

            app.add_customers(emails)

            mgmt.create.assert_has_calls(
                [call(user) for user in expected_created],
                any_order=True)

            args, kwargs = group.add_users.call_args
            assert list(args[0]) == expected_added

        assert_case(
            all_users=[],
            expected_created=map(new_user, emails),
            expected_added=list(map(existing_user, emails)))

        assert_case(
            all_users=[existing_user('test1@example.com')],
            expected_created=[new_user('test2@example.com')],
            expected_added=list(map(existing_user, emails)))

        assert_case(
            all_users=list(map(existing_user, emails)),
            expected_created=[],
            expected_added=list(map(existing_user, emails)))

    @patch('control_panel_api.auth0.Auth0Client')
    def test_delete_customers(self, mock_auth0_client):
        app = App.objects.create(repo_url='https://example.com/repo_name')
        auth0 = mock_auth0_client.return_value
        authz = auth0.authorization
        group = authz.get.return_value
        app.delete_customers(['email|123'])
        group.delete_users.assert_called_with([
            {'user_id': 'email|123'}])


class S3BucketTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.s3_bucket_1 = S3Bucket.objects.create(name="test-bucket-1")

    def test_arn(self):
        self.assertEqual(
            'arn:aws:s3:::test-bucket-1',
            self.s3_bucket_1.arn
        )

    @patch('control_panel_api.models.services.revoke_bucket_access')
    def test_delete_revokes_permissions(self, mock_revoke_bucket_access):
        users3bucket = mommy.make(
            'control_panel_api.UserS3Bucket',
            s3bucket=self.s3_bucket_1,
        )

        apps3bucket = mommy.make(
            'control_panel_api.AppS3Bucket',
            s3bucket=self.s3_bucket_1,
        )

        self.s3_bucket_1.delete()

        expected_revoke_calls = (
            call(self.s3_bucket_1.arn, users3bucket.aws_role_name()),
            call(self.s3_bucket_1.arn, apps3bucket.aws_role_name()),
        )
        mock_revoke_bucket_access.assert_has_calls(
            expected_revoke_calls,
            any_order=True,
        )

    @patch('control_panel_api.services.create_bucket')
    def test_bucket_create(self, mock_create_bucket):
        url = 'http://foo.com/'
        mock_create_bucket.return_value = {'Location': url}

        self.s3_bucket_1.aws_create()

        mock_create_bucket.assert_called_with(
            self.s3_bucket_1.name,
            self.s3_bucket_1.is_data_warehouse,
        )

        self.assertEqual(url, self.s3_bucket_1.location_url)

    @patch('control_panel_api.models.UserS3Bucket.aws_create')
    def test_create_users3bucket(self, mock_aws_create):
        self.s3_bucket_1.create_users3bucket(
            mommy.make('control_panel_api.User'))
        mock_aws_create.assert_called()


class AppS3BucketTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.app_1 = mommy.make('control_panel_api.App', name="app_1")
        cls.s3_bucket_1 = mommy.make(
            'control_panel_api.S3Bucket', name="test-bucket-1")

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

    @patch('control_panel_api.services.grant_bucket_access')
    def test_update_aws_permissions(self, mock_grant_bucket_access):
        apps3bucket = AppS3Bucket(
            app=self.app_1,
            s3bucket=self.s3_bucket_1,
            access_level=AppS3Bucket.READONLY,
        )

        apps3bucket.aws_update()

        mock_grant_bucket_access.assert_called_with(
            self.s3_bucket_1.arn,
            apps3bucket.has_readwrite_access(),
            self.app_1.iam_role_name
        )

    @patch('control_panel_api.services.grant_bucket_access')
    def test_aws_create(self, mock_grant_bucket_access):
        apps3bucket = AppS3Bucket(
            app=self.app_1,
            s3bucket=self.s3_bucket_1,
            access_level=AppS3Bucket.READONLY,
        )

        apps3bucket.aws_create()

        mock_grant_bucket_access.assert_called_with(
            self.s3_bucket_1.arn,
            apps3bucket.has_readwrite_access(),
            self.app_1.iam_role_name
        )

    @patch('control_panel_api.services.revoke_bucket_access')
    def test_delete_revoke_permissions(self, mock_revoke_bucket_access):
        apps3bucket = mommy.make(
            'control_panel_api.AppS3Bucket',
            app=self.app_1,
            s3bucket=self.s3_bucket_1,
            access_level=AppS3Bucket.READONLY,
        )

        apps3bucket.delete()

        mock_revoke_bucket_access.assert_called_with(
            self.s3_bucket_1.arn,
            self.app_1.iam_role_name,
        )

    def test_repo_name(self):
        app = mommy.prepare('control_panel_api.App')

        url_test_cases = (
            ('https://github.com/org/a_repo_name', 'a_repo_name'),
            ('git@github.com:org/repo_2.git', 'repo_2'),
            ('https://github.com/org/a_repo_name.git/', 'a_repo_name'),
            ('https://github.com/org/a_repo_name/', 'a_repo_name'),
            ('http://foo.com', 'foo.com'),
            ('http://foo.com/', 'foo.com'),
        )

        for url, expected in url_test_cases:
            app.repo_url = url
            self.assertEqual(expected, app._repo_name)


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

    @patch('control_panel_api.services.grant_bucket_access')
    def test_aws_create(self, mock_grant_bucket_access):
        self.users3bucket_1.aws_create()

        mock_grant_bucket_access.assert_called_with(
            self.s3_bucket_1.arn,
            self.users3bucket_1.has_readwrite_access(),
            self.user_1.iam_role_name,
        )

    @patch('control_panel_api.services.revoke_bucket_access')
    def test_delete_revoke_permissions(self, mock_revoke_bucket_access):
        self.users3bucket_1.delete()

        mock_revoke_bucket_access.assert_called_with(
            self.s3_bucket_1.arn,
            self.user_1.iam_role_name,
        )
