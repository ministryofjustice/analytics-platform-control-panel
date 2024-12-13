# Standard library
from unittest import mock

# Third-party
import pytest
from pytest_django.asserts import assertQuerySetEqual

# First-party/Local
from controlpanel.frontend.views import release


def test_release_detail_context_data():
    """
    Ensure the context data for the release detail view contains the expected
    list of beta users (if they exist).
    """
    v = release.ReleaseDetail()
    v.request = mock.MagicMock()
    v.request.method = "GET"
    mock_object = mock.MagicMock()
    mock_user1 = mock.MagicMock()
    mock_user2 = mock.MagicMock()
    mock_user1.username = "aldo"
    mock_user2.username = "nicholas"
    mock_object.target_users.all.return_value = [mock_user1, mock_user2]
    v.object = mock_object
    result = v.get_context_data()
    assert result["target_users"] == "aldo, nicholas"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "data, count",
    [
        ({}, 2),
        ({"chart_name": "rstudio"}, 1),
        ({"chart_name": "jupyter-lab"}, 1),
        ({"status": "restricted"}, 0),
        ({"status": "active"}, 2),
    ],
)
def test_release_list_get_context_data(rf, data, count):
    """
    Note: ToolRelease objects are created in data migration api/migrations/0010_DATA_add_tools.py
    """
    view = release.ReleaseList()
    view.request = rf.get("/releases/", data=data)
    view.object_list = view.get_queryset()
    context = view.get_context_data()

    assert "filter" in context
    assert "releases" in context
    assertQuerySetEqual(context["releases"], context["filter"].qs.distinct())
    assert context["releases"].count() == count
