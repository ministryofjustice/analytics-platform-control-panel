from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator


def validate_env_prefix(value):
    """Validate the name has env-prefix, check current set ENV value"""
    if not value.startswith(f"{settings.ENV}-"):
        raise ValidationError("Name must have correct env prefix e.g. {}-bucketname".format(settings.ENV))


# An S3 bucket name needs to be min 3 chars, max 63 chars long.
validate_s3_bucket_length = RegexValidator(
    regex='^.{3,63}$',
    message="must be between 3 and 63 characters",
)

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
    regex='^([a-z][a-z0-9-]*[a-z0-9])(.[a-z][a-z0-9-]*[a-z0-9])*$',
    message="is invalid, check AWS S3 bucket names restrictions (for example, ""can only contains letters, digits, dots and hyphens)",
)


def validate_github_repository_url(value):
    github_base_url = "https://github.com/"

    if not value.startswith(github_base_url):
        raise ValidationError("Must be a Github hosted repository")

    repo_name = value[len(github_base_url):]
    org, _ = repo_name.split("/", 1)

    if org not in settings.GITHUB_ORGS:
        orgs = ", ".join(settings.GITHUB_ORGS)
        raise ValidationError(
            f"Unknown Github organization, must be one of {orgs}",
        )
