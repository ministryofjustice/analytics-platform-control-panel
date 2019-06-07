from controlpanel.api.aws import S3AccessPolicy
from tests.api.iam_test_cases import IAMPolicyTestCase


class S3AccessTestCase(IAMPolicyTestCase):

    CONSOLE_ACTIONS = (
        's3:GetBucketLocation',
        's3:ListAllMyBuckets',
    )

    READ_ACTIONS = (
        's3:GetObject',
        's3:GetObjectAcl',
        's3:GetObjectVersion',
    )

    WRITE_ACTIONS = (
        's3:DeleteObject',
        's3:DeleteObjectVersion',
        's3:PutObject',
        's3:PutObjectAcl',
        's3:RestoreObject',
    )

    def assert_has_readwrite_access(self, document, arn):
        self._assert_can_list(document, arn)
        self._assert_can_read(document, arn)
        self._assert_can_write(document, arn)

    def assert_has_readonly_access(self, document, arn):
        self._assert_can_list(document, arn)
        self._assert_can_read(document, arn)
        self.assert_cannot_write(document, arn)

    def assert_can_access_console(self, document):
        for action in self.CONSOLE_ACTIONS:
            self.assert_allowed(document, action, 'arn:aws:s3:::*')

    def assert_cannot_list(self, document, resource):
        self.assert_not_allowed(document, 's3:ListBucket', resource)

    def assert_cannot_read(self, document, resource):
        for action in self.READ_ACTIONS:
            self.assert_not_allowed(document, action, f'{resource}/*')

    def assert_cannot_write(self, document, resource):
        for action in self.WRITE_ACTIONS:
            self.assert_not_allowed(document, action, f'{resource}/*')

    def _assert_can_list(self, document, resource):
        self.assert_allowed(document, 's3:ListBucket', resource)

    def _assert_can_read(self, document, resource):
        for action in self.READ_ACTIONS:
            self.assert_allowed(document, action, f'{resource}/*')

    def _assert_can_write(self, document, resource):
        for action in self.WRITE_ACTIONS:
            self.assert_allowed(document, action, f'{resource}/*')


class S3AccessPolicyTestCase(S3AccessTestCase):

    def test_blank_policy(self):
        policy = S3AccessPolicy()
        document = policy.document

        self.assert_can_access_console(document)
        self.assert_has_not_sid(document, 'list')
        self.assert_has_not_sid(document, 'readonly')
        self.assert_has_not_sid(document, 'readwrite')

    def test_granting_access(self):
        arns = (
            ('arn:aws:s3:::readonly-1', False),
            ('arn:aws:s3:::readonly-2', False),
            ('arn:aws:s3:::readwrite-1', True),
            ('arn:aws:s3:::readwrite-2', True),
        )

        policy = S3AccessPolicy()
        for (arn, readwrite) in arns:
            policy.grant_access(arn, readwrite=readwrite)

        document = policy.document
        self.assert_can_access_console(document)

        for (arn, readwrite) in arns:
            if readwrite:
                self.assert_has_readwrite_access(document, arn)
            else:
                self.assert_has_readonly_access(document, arn)

    def test_granting_access_again_with_different_level(self):
        ARN = 'arn:aws:s3:::test-bucket-1'

        policy = S3AccessPolicy()
        policy.grant_access(ARN, readwrite=True)

        document = policy.document
        self.assert_can_access_console(document)
        self.assert_has_readwrite_access(document, ARN)

        policy.grant_access(ARN, readwrite=False)

        document = policy.document
        self.assert_can_access_console(document)
        self.assert_has_readonly_access(document, ARN)

    def test_revoking_access(self):
        readonly_arn = 'arn:aws:s3:::readonly-1'
        readwrite_arn = 'arn:aws:s3:::readwrite-1'

        policy = S3AccessPolicy()
        policy.grant_access(readonly_arn, readwrite=False)
        policy.grant_access(readwrite_arn, readwrite=True)

        document = policy.document
        self.assert_can_access_console(document)
        self.assert_has_readonly_access(document, readonly_arn)
        self.assert_has_readwrite_access(document, readwrite_arn)

        policy.revoke_access(readwrite_arn)

        document = policy.document
        # access to `readwrite_arn` is now revoked
        self.assert_cannot_list(document, readwrite_arn)
        self.assert_cannot_read(document, readwrite_arn)
        self.assert_cannot_write(document, readwrite_arn)
        # existing permissions didn't change
        self.assert_can_access_console(document)
        self.assert_has_readonly_access(document, readonly_arn)

    def test_import_document(self):
        DOCUMENT = {
            'Version': '2012-10-17',
            'Statement': [
                {
                    'Sid': 'console',
                    'Effect': 'Allow',
                    'Action': [
                        's3:GetBucketLocation',
                        's3:ListAllMyBuckets',
                    ],
                    'Resource': 'arn:aws:s3:::*',
                },
                {
                    'Sid': 'list',
                    'Action': [
                        's3:ListBucket',
                    ],
                    'Effect': 'Allow',
                    'Resource': [
                        'arn:aws:s3:::readwrite-1',
                        'arn:aws:s3:::readwrite-2',
                        'arn:aws:s3:::readonly-1',
                    ],
                },
                {
                    'Sid': 'readonly',
                    'Action': [
                        's3:GetObject',
                        's3:GetObjectAcl',
                        's3:GetObjectVersion',
                    ],
                    'Effect': 'Allow',
                    'Resource': [
                        'arn:aws:s3:::readonly-1/*',
                    ],
                },
                {
                    'Sid': 'readwrite',
                    'Action': [
                        's3:GetObject',
                        's3:GetObjectAcl',
                        's3:GetObjectVersion',
                        's3:DeleteObject',
                        's3:DeleteObjectVersion',
                        's3:PutObject',
                        's3:PutObjectAcl',
                        's3:RestoreObject',
                    ],
                    'Effect': 'Allow',
                    'Resource': [
                        'arn:aws:s3:::readwrite-1/*',
                        'arn:aws:s3:::readwrite-2/*',
                    ]
                },
            ],
        }

        policy = S3AccessPolicy(document=DOCUMENT)
        document = policy.document

        readonly_arn = 'arn:aws:s3:::readonly-1'
        readwrite_arns = (
            'arn:aws:s3:::readwrite-1',
            'arn:aws:s3:::readwrite-2',
        )

        self.assert_can_access_console(document)
        self.assert_has_readonly_access(document, readonly_arn)
        for arn in readwrite_arns:
            self.assert_has_readwrite_access(document, arn)
