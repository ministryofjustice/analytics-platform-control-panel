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

# The RSA key below was generated specifically for the authentication tests only
PRIVATE_KEY = """-----BEGIN RSA PRIVATE KEY-----
MIICXAIBAAKBgQCo/FYLtMEuzwVf5n0ml+znmXF3hgj/i4W0ZndaL7GL1C+JpdQQ
yXGVKom2TyDMRPAwcL7D2shGO+dxAJQ0D2475Grk+rwBSBmtxea/glL7Fi6eMCKj
B7vwFf0jw8mDhjfKBtBKOdfEaEs7+0D32XCkYnq9IFoHfA1uQMhlVFdiBwIDAQAB
AoGABM0WjMKX8oKDPpRH3f7XBkV/ycuPGeOW6uc2YOOWAckHiLujaM6wYXKR8xIQ
dn1G7blmUh43LnepPbasf0Yo9ZLPKKbo/AMd8nS59Q0WHlIKUJ9DLnfxjpEzigZ4
PjEISBcmXbjg2Icq0b9xoeLC9X0aFEYbSGQJbA7L0snAOTECQQDgsKTxTxby1Ma4
SYdKwxhxchb4BD3NjvFAyx/FDmVHtbezOhng1va1TsM3aB95xIu8K8SNSSm/Hgi0
bDkVlVgLAkEAwIiN2EFXwioDjstyF8eC7leFoKKxykIZID+YerT6UoQd9Bu0trDe
Mh0RVsSW4D5Y/CjV5v5f5NT8eoDNKbiPdQJAV26lYHkkNu3xPfjuunrcYhjBM1WD
Lx/2ZP4lqKqHYrYle4qaU1GSws6ZTFAqH1oJ/fkSDOBxbDslq/+I3ws0LQJAIFAK
tkupJd4VQMbmPBVw5P1tYNtNSWu0edQSjC2JgYXI3So1NyAR+okkWtKdm777Aj78
P0tb3rTcNtcdF65w7QJBAIlfLWXrnjuJP4xdsJpubct+VoPZpEkojXp16zdEPSni
Tk1/Hf+kxTTBR5xfmgtLCPmOU8d+qodjxI6JmZtfvVU=
-----END RSA PRIVATE KEY-----"""

PUBLIC_KEY = """-----BEGIN PUBLIC KEY-----
MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQCo/FYLtMEuzwVf5n0ml+znmXF3
hgj/i4W0ZndaL7GL1C+JpdQQyXGVKom2TyDMRPAwcL7D2shGO+dxAJQ0D2475Grk
+rwBSBmtxea/glL7Fi6eMCKjB7vwFf0jw8mDhjfKBtBKOdfEaEs7+0D32XCkYnq9
IFoHfA1uQMhlVFdiBwIDAQAB
-----END PUBLIC KEY-----"""