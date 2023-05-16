# Third-party
import pytest


@pytest.fixture(autouse=True)
def enable_django_db_for_all_tests(transactional_db):
    pass


@pytest.fixture(autouse=True)
def login_superuser(client, superuser):
    client.force_login(superuser)
