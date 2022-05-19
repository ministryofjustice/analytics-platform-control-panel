import os
import tempfile

import django
import yaml
from django.core import management

if __name__ == "__main__":
    AWS_ACCESS_KEY_ID = os.environ.get("LANDING_AWS_ACCESS_KEY_ID")
    AWS_DATA_ROLE = os.environ.get("AWS_DATA_ROLE")
    AWS_DEV_ROLE = os.environ.get("AWS_DEV_ROLE")
    AWS_REGION = os.environ.get("AWS_REGION")
    AWS_SECRET_ACCESS_KEY = os.environ.get("LANDING_AWS_SECRET_ACCESS_KEY")
    AWS_MFA_SERIAL = os.environ.get("AWS_MFA_SERIAL")

    aws_config = f"""
    [profile landing]
    region={AWS_REGION}
    output=json
    mfa_serial={AWS_MFA_SERIAL}
    aws_access_key_id = {AWS_ACCESS_KEY_ID}
    aws_secret_access_key = {AWS_SECRET_ACCESS_KEY}

    [profile admin-data]
    region=eu-west-1
    role_arn={AWS_DATA_ROLE}
    source_profile=landing

    [profile admin-dev]
    region=eu-west-1
    role_arn={AWS_DEV_ROLE}
    source_profile=landing
    """


    with open(os.path.join(".aws", "config"), "w") as config_file:
        config_file.write(aws_config)
