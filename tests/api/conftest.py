import os
from unittest.mock import patch

from model_mommy import mommy
import pytest


@pytest.fixture
def superuser(db):
    return mommy.make(
        'api.User',
        auth0_id='github|user_1',
        is_superuser=True,
        username='alice',
    )


@pytest.fixture
def users(db, superuser):
    return {
        'superuser': superuser,
        'normal_user': mommy.make(
            'api.User',
            auth0_id='github|user_2',
            username="bob",
            is_superuser=False,
        ),
        "other_user": mommy.make(
            "api.User",
            username="carol",
            auth0_id="github|user_3",
        ),
    }
