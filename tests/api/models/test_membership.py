from django.db.utils import IntegrityError
from model_mommy import mommy
import pytest

from controlpanel.api.models import TeamMembership


@pytest.fixture
def users():
    return dict(zip(
        ("alice", "bob", "carol"),
        mommy.make('api.User', _quantity=3),
    ))


@pytest.fixture
def teams():
    return dict(zip(
        ("justice", "other"),
        mommy.make('api.Team', _quantity=2),
    ))


@pytest.fixture
def roles():
    return dict([
        (code, mommy.make('api.Role', code=code, name=code))
        for code in ('maintainer', 'member')
    ])


@pytest.fixture(autouse=True)
def memberships(users, teams, roles):
    # Add Alice to Justice team as maintainer
    TeamMembership.objects.create(
        team=teams["justice"],
        user=users["alice"],
        role=roles["maintainer"],
    )
    # Add Bob to Justice team as member
    TeamMembership.objects.create(
        team=teams["justice"],
        user=users["bob"],
        role=roles["member"],
    )
    # Add Carol to other team as member
    TeamMembership.objects.create(
        team=teams["other"],
        user=users["carol"],
        role=roles["member"],
    )


@pytest.mark.django_db
def test_get_user_teams(users, teams):
    alices_teams = users["alice"].teams.all()
    assert teams["justice"] in alices_teams
    assert teams["other"] not in alices_teams


@pytest.mark.django_db
def test_get_users_in_a_team(users, teams):
    justice_users = teams["justice"].users.all()
    assert users["alice"] in justice_users
    assert users["bob"] in justice_users
    assert users["carol"] not in justice_users


@pytest.mark.django_db
def test_get_users_with_a_role_in_team(users, teams):
    justice_maintainers = teams["justice"].users_with_role("maintainer")
    justice_members = teams["justice"].users_with_role("member")
    assert users["alice"] in justice_maintainers
    assert users["alice"] not in justice_members
    assert users["bob"] not in justice_maintainers
    assert users["bob"] in justice_members
    assert users["carol"] not in justice_maintainers
    assert users["carol"] not in justice_members


@pytest.mark.django_db
def test_user_can_be_added_to_team_only_once(users, teams, roles):
    with pytest.raises(IntegrityError):
        # (trying to) Add Alice to team justice again
        TeamMembership.objects.create(
            team=teams["justice"],
            user=users["alice"],
            role=roles["member"],
        )
