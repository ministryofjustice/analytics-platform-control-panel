#!/usr/bin/env python3
# Standard library
import os
import sys

# Third-party
import dotenv

# First-party/Local
from controlpanel.utils import load_app_conf_from_file

if __name__ == "__main__":
    dotenv.load_dotenv()

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "controlpanel.settings")

    load_app_conf_from_file()
    try:
        # Third-party
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)
