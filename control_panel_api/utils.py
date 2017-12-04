import re


def is_valid_dns_label(label):
    """
    A DNS-1123 label must consist of lower case alphanumeric characters or '-',
    and must start and end with an alphanumeric character
    """

    valid_dns_label = re.compile(r'^[a-z0-9]([-a-z0-9]*[a-z0-9])?$')

    return valid_dns_label.match(label) is not None


def sanitize_dns_label(label):

    # lowercase
    label = label.lower()

    # alphanumerics and hyphens
    label = re.sub(r'[^a-z0-9]+', '-', label)

    # must start with an alphanumeric
    label = re.sub(r'^[^a-z0-9]*', '', label)

    # label must be 63 chars or less
    label = label[:63]

    # make sure we end with an alphanumeric
    label = re.sub(r'[^a-z0-9]*$', '', label)

    return label
