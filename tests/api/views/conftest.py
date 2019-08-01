from unittest.mock import patch

from model_mommy import mommy
import pytest


@pytest.fixture(autouse=True)
def enable_django_db_for_all_tests(transactional_db):
    pass


@pytest.fixture
def users(superuser):
    return {
        'superuser': superuser,
        1: mommy.make(
            'api.User',
            auth0_id='github|1',
            is_superuser=False,
            username='bob',
        ),
        2: mommy.make(
            'api.User',
            auth0_id='github|2',
            is_superuser=False,
            username='carol',
        ),
    }


@pytest.fixture(autouse=True)
def login_superuser(client, superuser):
    client.force_login(superuser)

