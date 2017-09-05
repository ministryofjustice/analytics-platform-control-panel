from django.conf import settings

from . import aws

READ_WRITE = 'readwrite'
READ_ONLY = 'readonly'


def _bucket_name(name):
    """Prefix the bucket name with environment e.g. dev-james"""
    return "{}-{}".format(settings.ENV, name)


def _policy_name(name, readwrite=False):
    """Prefix the policy name with bucket name, postfix with access level e.g. dev-james-readwrite"""
    return "{}-{}".format(_bucket_name(name), READ_WRITE if readwrite else READ_ONLY)


def create_team_bucket(name):
    """Creates an s3 bucket and adds logging"""
    name = _bucket_name(name)
    aws.create_bucket(name, acl='private', region=settings.BUCKET_REGION)
    aws.put_bucket_logging(name, target_bucket=settings.LOGS_BUCKET_NAME, target_prefix="{}/".format(name))


def create_team_bucket_policies(name):
    """Creates readwrite and readonly policies for s3 bucket"""
    aws.create_policy(_policy_name(name, readwrite=True), readwrite=True)
    aws.create_policy(_policy_name(name, readwrite=False), readwrite=False)
