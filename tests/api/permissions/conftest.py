from model_mommy import mommy
import pytest


@pytest.fixture(autouse=True)
def users():
    return {
        'superuser': mommy.make(
            'api.User',
            auth0_id='github|user_1',
            username="alice",
            is_superuser=True,
        ),
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
