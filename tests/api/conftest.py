from model_mommy import mommy
import pytest


@pytest.fixture
def superuser():
    return mommy.make(
        'api.User',
        auth0_id='github|0',
        is_superuser=True,
        username='alice',
    )
