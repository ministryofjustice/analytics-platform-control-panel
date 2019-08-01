from unittest.mock import patch

from model_mommy import mommy
import pytest


@pytest.yield_fixture(autouse=True)
def aws():
    """
    Mock calls to AWS
    """
    with patch('controlpanel.api.cluster.aws') as aws:
        yield aws


@pytest.yield_fixture(autouse=True)
def elasticsearch():
    """
    Mock calls to Elasticsearch
    """
    with patch('controlpanel.api.elasticsearch.Elasticsearch') as es:
        yield es.return_value


@pytest.yield_fixture(autouse=True)
def github():
    """
    Mock calls to Github
    """
    with patch('controlpanel.api.cluster.Github') as Github:
        yield Github.return_value


@pytest.yield_fixture(autouse=True)
def helm():
    """
    Mock calls to Helm
    """
    with patch('controlpanel.api.cluster.helm') as helm:
        yield helm


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

