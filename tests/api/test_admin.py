# Standard library
import csv
from datetime import datetime
from io import StringIO
from unittest.mock import Mock, patch

# Third-party
import pytest
from django.contrib.admin.sites import AdminSite
from django.http import HttpRequest, HttpResponse
from django.utils import timezone
from model_bakery import baker

# First-party/Local
from controlpanel.api.admin import ToolDeploymentAdmin, UserAdmin, export_as_csv
from controlpanel.api.models import Tool, ToolDeployment, User


@pytest.mark.django_db
class TestExportAsCsvFunction:
    """Test the standalone export_as_csv function."""

    @patch("controlpanel.api.admin.timezone.now")
    def test_export_with_data(self, mock_now):
        """Test CSV export with valid data."""
        mock_now.return_value = datetime(2025, 8, 22, 14, 30, 0)

        test_data = [
            {"name": "John", "email": "john@example.com", "age": 30},
            {"name": "Jane", "email": "jane@example.com", "age": 25},
        ]

        response = export_as_csv("test_users", test_data)

        assert isinstance(response, HttpResponse)
        assert response["Content-Type"] == "text/csv"
        assert (
            response["Content-Disposition"]
            == "attachment; filename=test_users_2025-08-22_14-30-00.csv"
        )

        # Parse CSV content
        content = response.content.decode("utf-8")
        csv_reader = csv.DictReader(StringIO(content))
        rows = list(csv_reader)

        assert len(rows) == 2
        assert rows[0]["name"] == "John"
        assert rows[0]["email"] == "john@example.com"
        assert rows[0]["age"] == "30"
        assert rows[1]["name"] == "Jane"

    @patch("controlpanel.api.admin.timezone.now")
    def test_export_with_empty_data(self, mock_now):
        """Test CSV export with empty data."""
        mock_now.return_value = datetime(2025, 8, 22, 14, 30, 0)

        response = export_as_csv("empty_file", [])

        assert isinstance(response, HttpResponse)
        assert response["Content-Type"] == "text/csv"
        assert (
            response["Content-Disposition"]
            == "attachment; filename=empty_file_2025-08-22_14-30-00.csv"
        )

        # Should have only header row (which is empty)
        content = response.content.decode("utf-8")
        assert content.strip() == ""

    def test_filename_timestamp_format(self):
        """Test that filename includes properly formatted timestamp."""
        test_data = [{"field": "value"}]

        with patch("controlpanel.api.admin.timezone.now") as mock_now:
            mock_now.return_value = datetime(2025, 12, 31, 23, 59, 59)
            response = export_as_csv("test", test_data)

            assert "test_2025-12-31_23-59-59.csv" in response["Content-Disposition"]


@pytest.mark.django_db
class TestUserAdminExportAction:
    """Test the UserAdmin export_as_csv action."""

    def setup_method(self):
        self.site = AdminSite()
        self.admin = UserAdmin(User, self.site)
        self.request = HttpRequest()
        self.request.user = baker.make(User, is_superuser=True)

    def test_export_users_csv_fields(self):
        """Test that the correct user fields are exported."""
        user1 = baker.make(
            User,
            username="testuser1",
            email="test1@example.com",
            justice_email="test1@justice.gov.uk",
            name="Test User 1",
            auth0_id="auth0_123",
            azure_oid="azure_456",
        )
        user2 = baker.make(
            User,
            username="testuser2",
            email="test2@example.com",
            justice_email="test2@justice.gov.uk",
            name="Test User 2",
            auth0_id="auth0_789",
            azure_oid="azure_012",
        )

        queryset = User.objects.filter(pk__in=[user1.pk, user2.pk])

        with patch("controlpanel.api.admin.export_as_csv") as mock_export:
            mock_export.return_value = HttpResponse()

            self.admin.export_as_csv(self.request, queryset)

            # Verify export_as_csv was called with correct arguments
            assert mock_export.call_count == 1
            assert mock_export.call_args.kwargs["filename"] == "users"

            row_data = mock_export.call_args.kwargs["row_data"]
            assert len(row_data) == 2

            # Check first user data
            user1_data = row_data[0]
            expected_fields = {
                "username",
                "alpha_role_arn",
                "k8s_namespace",
                "email",
                "justice_email",
                "auth0_id",
                "name",
                "azure_oid",
                "date_joined",
            }
            assert set(user1_data.keys()) == expected_fields
            assert user1_data["username"] == "testuser1"
            assert user1_data["email"] == "test1@example.com"
            assert user1_data["justice_email"] == "test1@justice.gov.uk"

    def test_export_users_csv_empty_queryset(self):
        """Test export with empty user queryset."""
        queryset = User.objects.none()

        with patch("controlpanel.api.admin.export_as_csv") as mock_export:
            mock_export.return_value = HttpResponse()

            self.admin.export_as_csv(self.request, queryset)

            assert mock_export.call_args.kwargs["filename"] == "users"
            assert len(mock_export.call_args.kwargs["row_data"]) == 0

    def test_export_users_csv_action_description(self):
        """Test that the action has the correct description."""
        assert self.admin.export_as_csv.short_description == "Export selected users as CSV"


@pytest.mark.django_db
class TestToolDeploymentAdminExportAction:
    """Test the ToolDeploymentAdmin export_as_csv action."""

    def setup_method(self):
        self.site = AdminSite()
        self.admin = ToolDeploymentAdmin(ToolDeployment, self.site)
        self.request = HttpRequest()
        self.request.user = baker.make(User, is_superuser=True)

    def test_export_tool_deployments_csv_fields(self):
        """Test that the correct tool deployment fields are exported."""
        user = baker.make(
            User, username="testuser", email="test@example.com", justice_email="test@justice.gov.uk"
        )
        tool = baker.make(
            Tool,
            name="rstudio",
            version="1.0.0",
            image_tag="latest",
            description="RStudio Tool",
            is_retired=False,
            is_deprecated=False,
        )
        deployment = baker.make(
            ToolDeployment,
            user=user,
            tool=tool,
            tool_type="rstudio",
            is_active=True,
        )

        queryset = ToolDeployment.objects.filter(pk=deployment.pk)

        with patch("controlpanel.api.admin.export_as_csv") as mock_export:
            mock_export.return_value = HttpResponse()

            self.admin.export_as_csv(self.request, queryset)

            # Verify export_as_csv was called
            assert mock_export.call_count == 1
            row_data = mock_export.call_args.kwargs["row_data"]

            assert mock_export.call_args.kwargs["filename"] == "tool_deployments"
            assert len(row_data) == 1

            # Check deployment data
            deployment_data = row_data[0]
            expected_fields = {
                "username",
                "tool_type",
                "image_tag",
                "chart_version",
                "description",
                "email",
                "justice_email",
                "is_active",
                "is_retired",
                "is_deprecated",
                "created",
            }
            assert set(deployment_data.keys()) == expected_fields
            assert deployment_data["username"] == "testuser"
            assert deployment_data["tool_type"] == "rstudio"
            assert deployment_data["image_tag"] == "latest"
            assert deployment_data["chart_version"] == "1.0.0"
            assert deployment_data["description"] == "RStudio Tool"
            assert deployment_data["email"] == "test@example.com"
            assert deployment_data["justice_email"] == "test@justice.gov.uk"
            assert deployment_data["is_active"] is True
            assert deployment_data["is_retired"] is False
            assert deployment_data["is_deprecated"] is False

    def test_export_uses_select_related_optimization(self):
        """Test that the export optimizes database queries with select_related."""
        user = baker.make(User)
        tool = baker.make(Tool)
        deployment = baker.make(ToolDeployment, user=user, tool=tool)

        queryset = ToolDeployment.objects.filter(pk=deployment.pk)

        with patch("controlpanel.api.admin.export_as_csv") as mock_export:
            mock_export.return_value = HttpResponse()

            # Patch the queryset to spy on select_related calls
            with patch.object(queryset, "select_related") as mock_select_related:
                mock_select_related.return_value = queryset

                self.admin.export_as_csv(self.request, queryset)

                # Verify select_related was called with correct arguments
                mock_select_related.assert_called_once_with("user", "tool")

    def test_export_tool_deployments_empty_queryset(self):
        """Test export with empty tool deployment queryset."""
        queryset = ToolDeployment.objects.none()

        with patch("controlpanel.api.admin.export_as_csv") as mock_export:
            mock_export.return_value = HttpResponse()

            self.admin.export_as_csv(self.request, queryset)

            row_data = mock_export.call_args.kwargs["row_data"]
            assert mock_export.call_args.kwargs["filename"] == "tool_deployments"
            assert len(row_data) == 0


@pytest.mark.django_db
class TestAdminIntegration:
    """Integration tests for admin actions."""

    def test_user_admin_has_export_action(self):
        """Test that UserAdmin includes the export action."""
        site = AdminSite()
        admin = UserAdmin(User, site)

        assert "export_as_csv" in admin.actions
        assert hasattr(admin, "export_as_csv")

    def test_tool_deployment_admin_has_export_action(self):
        """Test that ToolDeploymentAdmin includes the export action."""
        site = AdminSite()
        admin = ToolDeploymentAdmin(ToolDeployment, site)

        assert "export_as_csv" in admin.actions
        assert hasattr(admin, "export_as_csv")

    def test_user_admin_export_end_to_end(self):
        """End-to-end test of user export functionality."""
        site = AdminSite()
        admin = UserAdmin(User, site)
        request = HttpRequest()
        request.user = baker.make(User, is_superuser=True)

        user = baker.make(User, username="testuser", email="test@example.com", name="Test User")
        queryset = User.objects.filter(pk=user.pk)

        response = admin.export_as_csv(request, queryset)

        assert isinstance(response, HttpResponse)
        assert response["Content-Type"] == "text/csv"
        assert "users_" in response["Content-Disposition"]

        # Verify CSV content contains the user data
        content = response.content.decode("utf-8")
        assert "testuser" in content
        assert "test@example.com" in content

    def test_tool_deployment_admin_export_end_to_end(self):
        """End-to-end test of tool deployment export functionality."""
        site = AdminSite()
        admin = ToolDeploymentAdmin(ToolDeployment, site)
        request = HttpRequest()
        request.user = baker.make(User, is_superuser=True)

        user = baker.make(User, username="testuser", email="test@example.com")
        tool = baker.make(Tool, name="rstudio", version="1.0.0", image_tag="latest")
        deployment = baker.make(
            ToolDeployment, user=user, tool=tool, tool_type="rstudio", is_active=True
        )
        queryset = ToolDeployment.objects.filter(pk=deployment.pk)

        response = admin.export_as_csv(request, queryset)

        assert isinstance(response, HttpResponse)
        assert response["Content-Type"] == "text/csv"
        assert "tool_deployments_" in response["Content-Disposition"]

        # Verify CSV content contains the deployment data
        content = response.content.decode("utf-8")
        assert "testuser" in content
        assert "rstudio" in content
        assert "latest" in content
