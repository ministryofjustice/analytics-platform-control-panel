from django.conf import settings


POLICY_DOCUMENT_READWRITE = {
    'Version': '2012-10-17',
    'Statement': [
        {'Sid': 'ListBucketsInConsole', 'Effect': 'Allow', 'Action': ['s3:GetBucketLocation', 's3:ListAllMyBuckets'],
         'Resource': 'arn:aws:s3:::*'},
        {'Sid': 'ListObjects', 'Action': ['s3:ListBucket'], 'Effect': 'Allow', 'Resource': [
            'arn:aws:s3:::test-bucketname']},
        {'Sid': 'ReadObjects', 'Action': ['s3:GetObject', 's3:GetObjectAcl', 's3:GetObjectVersion'], 'Effect': 'Allow',
         'Resource': 'arn:aws:s3:::test-bucketname/*'},
        {'Sid': 'UpdateRenameAndDeleteObjects',
         'Action': ['s3:DeleteObject', 's3:DeleteObjectVersion', 's3:PutObject',
                    's3:PutObjectAcl', 's3:RestoreObject'], 'Effect': 'Allow', 'Resource': 'arn:aws:s3:::test-bucketname/*'}
    ]
}

POLICY_DOCUMENT_READONLY = {
    'Version': '2012-10-17',
    'Statement': [
        {'Sid': 'ListBucketsInConsole', 'Effect': 'Allow', 'Action': ['s3:GetBucketLocation', 's3:ListAllMyBuckets'],
         'Resource': 'arn:aws:s3:::*'},
        {'Sid': 'ListObjects', 'Action': ['s3:ListBucket'], 'Effect': 'Allow', 'Resource': [
            'arn:aws:s3:::test-bucketname']},
        {'Sid': 'ReadObjects', 'Action': ['s3:GetObject', 's3:GetObjectAcl', 's3:GetObjectVersion'], 'Effect': 'Allow',
         'Resource': 'arn:aws:s3:::test-bucketname/*'}
    ]
}

APP_IAM_ROLE_ASSUME_POLICY = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {
                "Service": "ec2.amazonaws.com",
            },
            "Action": "sts:AssumeRole",
        },
        {
            "Effect": "Allow",
            "Principal": {
                "AWS": f"{settings.IAM_ARN_BASE}:role/{settings.K8S_WORKER_ROLE_NAME}",
            },
            "Action": "sts:AssumeRole",
        }
    ]
}

USER_IAM_ROLE_ASSUME_POLICY = {
    'Version': '2012-10-17',
    'Statement': [
        {
            'Effect': 'Allow',
            'Principal': {
                'Service': 'ec2.amazonaws.com'
            },
            'Action': 'sts:AssumeRole'
        },
        {
            'Effect': 'Allow',
            'Principal': {
                "AWS": f"{settings.IAM_ARN_BASE}:role/{settings.K8S_WORKER_ROLE_NAME}",
            },
            'Action': 'sts:AssumeRole'
        },
        {
            'Effect': 'Allow',
            'Principal': {
                'Federated': f"{settings.IAM_ARN_BASE}:saml-provider/{settings.SAML_PROVIDER}"
            },
            'Action': 'sts:AssumeRoleWithSAML',
            'Condition': {
                'StringEquals': {
                    'SAML:aud': 'https://signin.aws.amazon.com/saml'
                }
            }
        }
    ]
}
