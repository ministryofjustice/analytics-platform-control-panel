# Standard library
from unittest.mock import MagicMock, patch

# Third-party
import pytest
from django.core.management import call_command

# First-party/Local
from controlpanel.api.models import User


@pytest.fixture
def mock_user():
    user = MagicMock(spec=User)
    return user


@pytest.mark.parametrize(
    "filename,content",
    [
        ("users.txt", "user1\nuser2\nuser3\n"),
        ("users.txt", "user1\n\nuser2\n"),  # with blank lines
    ],
    ids=["txt_basic", "txt_with_blanks"],
)
@patch.object(User.objects, "get")
def test_delete_users_txt_file(mock_get, mock_user, tmp_path, filename, content):
    """Test that .txt files are parsed correctly and delete is called for each user."""
    mock_get.return_value = mock_user

    filepath = tmp_path / filename
    filepath.write_text(content)

    call_command("delete_users", str(filepath))

    expected_usernames = [u for u in content.strip().split("\n") if u]
    assert mock_get.call_count == len(expected_usernames)
    assert mock_user.delete.call_count == len(expected_usernames)


@patch.object(User.objects, "get")
def test_delete_users_csv_file(mock_get, mock_user, tmp_path):
    """Test that .csv files are parsed correctly using the username column."""
    mock_get.return_value = mock_user

    filepath = tmp_path / "users.csv"
    filepath.write_text("username,email\nuser1,a@b.com\nuser2,c@d.com\n")

    call_command("delete_users", str(filepath))

    assert mock_get.call_count == 2
    assert mock_user.delete.call_count == 2


@patch.object(User.objects, "get")
def test_delete_users_csv_custom_column(mock_get, mock_user, tmp_path):
    """Test that --column flag works for CSV files."""
    mock_get.return_value = mock_user

    filepath = tmp_path / "users.csv"
    filepath.write_text("name,user_id\nuser1,1\nuser2,2\n")

    call_command("delete_users", str(filepath), "--column", "name")

    assert mock_get.call_count == 2
    assert mock_user.delete.call_count == 2


def test_delete_users_csv_missing_column(tmp_path, capsys):
    """Test that an error is raised when the specified column is not in the CSV."""
    filepath = tmp_path / "users.csv"
    filepath.write_text("name,email\nuser1,a@b.com\n")

    call_command("delete_users", str(filepath), "--column", "username")

    captured = capsys.readouterr()
    assert "Column 'username' not found in CSV" in captured.err


def test_delete_users_unsupported_file_type(tmp_path, capsys):
    """Test that an error is raised for unsupported file types."""
    filepath = tmp_path / "users.json"
    filepath.write_text('{"users": ["user1"]}')

    call_command("delete_users", str(filepath))

    captured = capsys.readouterr()
    assert "Unsupported file type" in captured.err


def test_delete_users_file_not_found(capsys):
    """Test that an error is raised when the file does not exist."""
    call_command("delete_users", "/nonexistent/path/users.txt")

    captured = capsys.readouterr()
    assert "File not found" in captured.err


@patch.object(User.objects, "get")
def test_delete_users_user_not_found(mock_get, tmp_path, capsys):
    """Test that a warning is printed when a user is not found."""
    mock_get.side_effect = User.DoesNotExist

    filepath = tmp_path / "users.txt"
    filepath.write_text("nonexistent_user\n")

    call_command("delete_users", str(filepath))

    captured = capsys.readouterr()
    assert "User not found: nonexistent_user" in captured.out
