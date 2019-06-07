import re

from django.template.defaultfilters import slugify


def github_repository_name(url):
    """
    Get the repository name from a Github URL
    """
    repo = url.rstrip("/")

    if repo.endswith(".git"):
        repo = repo[:-4]

    _, name = repo.rsplit("/", 1)

    return name


def is_truthy(value):
    return str(value).lower() not in ("", "n", "no", "off", "false", "0")


def s3_slugify(name):
    """
    Create a slug using standard Django slugify, but replace underscores with
    hyphens so that it's valid for S3
    """
    return re.sub(r"_+", "-", slugify(name))


def sanitize_dns_label(label):
    label = label.lower()

    # labels may contain only letters, digits and hyphens
    label = re.sub(r"[^a-z0-9]+", "-", label)

    # labels must start with an alphanumeric character
    label = re.sub(r"^[^a-z0-9]*", "", label)

    # labels must be max 63 chars
    label = label[:63]

    # labels must end with an alphanumeric character
    label = re.sub(r"[^a-z0-9]*$", "", label)

    return label


def sanitize_environment_variable(s):
    return name.upper().replace("-", "_")
