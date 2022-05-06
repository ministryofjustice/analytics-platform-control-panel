#!/bin/bash
set -euo pipefail
python scripts/prepare_dev_tools.py
python manage.py loaddata controlpanel/api/dev_fixtures/tool_configured.yaml
