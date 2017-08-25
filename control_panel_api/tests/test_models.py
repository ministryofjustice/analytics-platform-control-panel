from django.test import TestCase

from control_panel_api.models import (
    Role,
    Team,
    TeamMembership,
    User,
)


class FixtureTestCase(TestCase):

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


class UserTest(FixtureTestCase):

    def test_teams(self):
        alices_teams = self.user_alice.teams()

        assert self.team_justice in alices_teams
        assert self.team_other not in alices_teams


class TeamTest(FixtureTestCase):

    def test_users(self):
        justice_users = self.team_justice.users()

        assert self.user_alice in justice_users
        assert self.user_bob in justice_users
        assert self.user_other not in justice_users

    def test_users_with_role(self):
        justice_maintainers = self.team_justice.users_with_role("maintainer")
        justice_members = self.team_justice.users_with_role("member")

        assert self.user_alice in justice_maintainers
        assert self.user_alice not in justice_members
        assert self.user_bob not in justice_maintainers
        assert self.user_bob in justice_members
        assert self.user_other not in justice_maintainers
        assert self.user_other not in justice_members
