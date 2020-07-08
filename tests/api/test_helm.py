from datetime import datetime, timedelta
import pytest
from unittest.mock import MagicMock, patch

from controlpanel.api.helm import (
    Chart,
    helm,
    HelmRepository,
)


def setup_function(fn):
    print("Resetting HelmRepository._updated_at ...")
    HelmRepository._updated_at = None


def test_chart_app_version():
    app_version = "RStudio: 1.2.1335+conda, R: 3.5.1, Python: 3.7.1, patch: 10"
    chart = Chart(
        "rstudio", "RStudio with Auth0 authentication proxy", "2.2.5", app_version,
    )

    assert chart.app_version == app_version


def test_helm_repository_update_when_recently_updated(helm_repository_index):
    HelmRepository._updated_at = datetime.utcnow()

    with patch("controlpanel.api.helm.Helm") as helm:
        HelmRepository.update(force=False)
        helm.execute.assert_not_called()


def test_helm_repository_update_when_cache_old(helm_repository_index):
    yesterday = datetime.utcnow() - timedelta(days=1)
    HelmRepository._updated_at = yesterday

    with patch("controlpanel.api.helm.Helm") as helm:
        HelmRepository.update(force=False)
        helm.execute.assert_called_once()


def test_helm_repository_chart_info_when_chart_not_found(helm_repository_index):
    with patch("controlpanel.api.helm.open", helm_repository_index):
        info = HelmRepository.get_chart_info("notfound")
        assert info == {}


def test_helm_repository_chart_info_when_chart_found(helm_repository_index):
    with patch("controlpanel.api.helm.open", helm_repository_index):
        # See tests/api/fixtures/helm_mojanalytics_index.py
        rstudio_info = HelmRepository.get_chart_info("rstudio")

        rstudio_2_2_5_app_version = (
            "RStudio: 1.2.1335+conda, R: 3.5.1, Python: 3.7.1, patch: 10"
        )

        assert len(rstudio_info) == 2
        assert "2.2.5" in rstudio_info
        assert "1.0.0" in rstudio_info

        assert rstudio_info["2.2.5"].app_version == rstudio_2_2_5_app_version
        # Helm added `appVersion` field in metadata only
        # "recently" so for testing that for old chart
        # version this returns `None`
        assert rstudio_info["1.0.0"].app_version == None


@pytest.mark.parametrize(
    "chart_name, version, expected_app_version",
    [
        ("notfound", "v42", None),
        ("rstudio", "unknown-version", None),
        ("rstudio", "1.0.0", None),
        (
            "rstudio",
            "2.2.5",
            "RStudio: 1.2.1335+conda, R: 3.5.1, Python: 3.7.1, patch: 10",
        ),
    ],
    ids=[
        "unknown-chart",
        "unknown-version",
        "chart-with-no-appVersion",
        "chart-with-appVersion",
    ],
)
def test_helm_repository_get_chart_app_version(
    helm_repository_index, chart_name, version, expected_app_version
):
    # See tests/api/fixtures/helm_mojanalytics_index.py
    with patch("controlpanel.api.helm.open", helm_repository_index):
        app_version = HelmRepository.get_chart_app_version(chart_name, version)
        assert app_version == expected_app_version


def test_helm_upgrade_release():
    helm.__class__.execute = MagicMock()

    upgrade_args = (
        "release-name",
        "helm-chart-name",
        "--namespace=user-alice",
        "--set=username=alice",
    )
    helm.upgrade_release(*upgrade_args)

    helm.__class__.execute.assert_called_with(
        "upgrade", "--install", "--wait", "--force", *upgrade_args,
    )


def test_helm_reset_home():
    helm.__class__.execute = MagicMock()
    reset_args = (
        "release-name",
        "helm-chart-name",
        "--namespace=user-alice",
        "--set=username=alice",
    )
    helm.reset_home(*reset_args)
    helm.__class__.execute.assert_called_with(
        "upgrade", "--install", *reset_args,
    )
