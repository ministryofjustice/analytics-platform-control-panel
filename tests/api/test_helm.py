from datetime import datetime, timedelta
import pytest
from unittest.mock import MagicMock, patch

from controlpanel.api import helm


def test_chart_app_version():
    app_version = "RStudio: 1.2.1335+conda, R: 3.5.1, Python: 3.7.1, patch: 10"
    chart = helm.HelmChart(
        "rstudio", "RStudio with Auth0 authentication proxy", "2.2.5", app_version,
    )

    assert chart.app_version == app_version


def test_helm_repository_chart_info_when_chart_not_found(helm_repository_index):
    with patch("builtins.open", helm_repository_index):
        info = helm.get_chart_info("notfound")
        assert info == {}


def test_helm_repository_chart_info_when_chart_found(helm_repository_index):
    with patch("builtins.open", helm_repository_index):
        # See tests/api/fixtures/helm_mojanalytics_index.py
        rstudio_info = helm.get_chart_info("rstudio")

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
    with patch("builtins.open", helm_repository_index):
        app_version = helm.get_chart_app_version(chart_name, version)
        assert app_version == expected_app_version


def test_helm_upgrade_release():
    helm._execute = MagicMock()

    upgrade_args = (
        "release-name",
        "helm-chart-name",
        "--namespace=user-alice",
        "--set=username=alice",
    )
    helm.upgrade_release(*upgrade_args)

    helm._execute.assert_called_with(
        "upgrade", "--install", "--wait", "--force", *upgrade_args,
    )
