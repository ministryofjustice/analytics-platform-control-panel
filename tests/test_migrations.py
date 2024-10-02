# Standard library
from io import StringIO

# Third-party
import pytest
from django.core.management import call_command


@pytest.mark.django_db
def test_no_pending_migrations():
    out = StringIO()
    try:
        call_command(
            "makemigrations",
            "--dry-run",
            "--check",
            stdout=out,
            stderr=StringIO(),
        )
    except SystemExit:
        raise AssertionError(f"Pending migrations: {out.getvalue()}") from None
