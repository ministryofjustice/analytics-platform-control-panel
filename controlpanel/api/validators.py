# Standard library
import ipaddress

# Third-party
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator

# First-party/Local
from controlpanel.api import cluster


def validate_env_prefix(value):
    """Validate the name has env-prefix, check current set ENV value"""
    if not value.startswith(f"{settings.ENV}-"):
        raise ValidationError(
            "Name must have correct env prefix e.g. {}-bucketname".format(settings.ENV)
        )


# An S3 bucket name needs to be min 3 chars, max 63 chars long.
validate_s3_bucket_length = RegexValidator(
    regex="^.{3,63}$",
    message="must be between 3 and 63 characters",
)


class ValidatorS3Bucket(object):
    def __init__(self, bucket_owner):
        self.bucket_owner = bucket_owner

    def __call__(self, value):
        if cluster.S3Bucket(None).exists(value, bucket_owner=self.bucket_owner):
            raise ValidationError(
                f"'{value}' already exists",
            )
        else:
            return value


# See: AWS' Bucket Restrictions and Limitations
# http://docs.aws.amazon.com/en_gb/AmazonS3/latest/dev/BucketRestrictions.html
#
# A label starts with a letter (preventing labels starting with digits to
# avoid IP-like names) and ends with a letter or a digit. It has 0+
# letters, digits or hyphens in the middle
#
# An S3 bucket name starts with a label, it can have more than one label
# separated by a dot.
validate_s3_bucket_labels = RegexValidator(
    regex="^([a-z][a-z0-9-]*[a-z0-9])(\\.[a-z][a-z0-9-]*[a-z0-9])*\\Z",
    message="is invalid, check AWS S3 bucket names restrictions (for example, "
    "can only contains letters, digits, dots and hyphens)",
)


validate_auth0_conn_name = RegexValidator(
    regex="^([a-zA-Z0-9][a-zA-Z0-9-]*[a-zA-Z0-9])$",
    message="is invalid, check Auth0 connection name restrictions (for example, "
    "can only start and end with alphanumeric alphanumeric, only contain alphanumeric and hyphens)",  # noqa: E501
)


validate_auth0_client_id = RegexValidator(
    regex="^([_a-zA-Z0-9-]*)$",
    message="is invalid, check Auth0 client_id restrictions (for example, "
    "can only contain alphanumeric, underscores and hyphens)",
)

validate_aws_role_arn = RegexValidator(
    regex=r"^arn:aws:iam::[0-9]{12}:role/[a-zA-Z0-9-_]+$",
    message=(
        "ARN is invalid. Check AWS ARN format "
        "(for example, 'arn:aws:iam::123456789012:role/role_name')"
    ),
)


def validate_github_repository_url(value):
    github_base_url = "https://github.com/"

    if not value.startswith(github_base_url):
        raise ValidationError("Must be a Github hosted repository")

    if value[-1] == "/":
        raise ValidationError("Repository URL should not include a trailing slash")

    repo_name = value[len(github_base_url) :]  # noqa: E203
    repo_parts = list(filter(None, repo_name.split("/")))
    if len(repo_parts) > 2:
        raise ValidationError("Repository URL should not include subdirectories")

    if len(repo_parts) < 2:
        raise ValidationError("Repository URL is missing the repository name")

    org = repo_parts[0]
    if org not in settings.GITHUB_ORGS:
        orgs = ", ".join(settings.GITHUB_ORGS)
        raise ValidationError(
            f"Unknown Github organization, must be one of {orgs}",
        )


def validate_ip_ranges(value):
    ip_ranges = value.split(",")
    for ip_range in ip_ranges:
        ip_range = ip_range.strip()
        try:
            ipaddress.ip_network(ip_range)
        except ValueError:
            raise ValidationError(
                (
                    "%(ip_r)s should be an IPv4 or IPv6 address (in a comma-separated list if several IP addresses are provided)."  # noqa: E501
                ),
                code="invalid",
                params={"ip_r": ip_range},
            )
