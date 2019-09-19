from unittest.mock import patch

from model_mommy import mommy
import pytest

from controlpanel.api.cluster import (
    BASE_ROLE_POLICY,
    App,
)
from controlpanel.api import models

from django.conf import settings


@pytest.fixture
def app_model():
    return models.App(slug = "slug")


@pytest.fixture
def app(app_model):
    return App(app_model)


def test_app_iam_role_name(app, app_model):
    expected_iam_role_name = f"{settings.ENV}_app_{app_model.slug}"
    assert app.iam_role_name == expected_iam_role_name


def test_app_create_iam_role(aws, app):
    app.create_iam_role()

    aws.create_role.assert_called_with(
        app.iam_role_name,
        BASE_ROLE_POLICY,
    )


def test_app_delete_iam_role(aws, app):
    app.delete_iam_role()
    aws.delete_role.assert_called_with(app.iam_role_name)
