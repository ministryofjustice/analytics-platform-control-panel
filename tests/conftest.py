from unittest.mock import patch

import pytest


@pytest.yield_fixture(autouse=True)
def aws():
    """
    Mock calls to AWS
    """
    with patch('controlpanel.api.cluster.aws') as aws:
        yield aws


@pytest.yield_fixture(autouse=True)
def helm():
    """
    Mock calls to Helm
    """
    with patch('controlpanel.api.cluster.helm') as helm:
        yield helm
