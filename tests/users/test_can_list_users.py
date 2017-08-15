import pytest

from django.contrib.auth.models import User


@pytest.yield_fixture
def given_there_are_users_in_db():
    User(email="john.doe@example.com").save()


@pytest.mark.usefixtures(
    'given_there_are_users_in_db'
)
@pytest.mark.django_db
def test_can_list_users():
    users = User.objects.all()
    assert users
