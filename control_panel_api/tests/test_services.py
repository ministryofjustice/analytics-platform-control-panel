from django.test.testcases import SimpleTestCase, override_settings

from control_panel_api import services


class ServicesTestCase(SimpleTestCase):
    def test_policy_document_readwrite(self):
        document = services.get_policy_document('foo', readwrite=True)

        sids = [s['Sid'] for s in document['Statement']]
        self.assertIn('UpdateRenameAndDeleteObjects', sids)

        document = services.get_policy_document('foo', readwrite=False)

        sids = [s['Sid'] for s in document['Statement']]
        self.assertNotIn('UpdateRenameAndDeleteObjects', sids)


@override_settings(ENV='test', IAM_ARN_BASE='arn:aws:iam::1337')
class NamingTestCase(SimpleTestCase):
    def test_bucket_name_has_env(self):
        self.assertEqual('test-bucketname', services._bucket_name('bucketname'))

    def test_policy_name_has_readwrite(self):
        self.assertEqual('bucketname-readonly', services._policy_name('bucketname', readwrite=False))
        self.assertEqual('bucketname-readwrite', services._policy_name('bucketname', readwrite=True))

    def test_policy_arn(self):
        self.assertEqual('arn:aws:iam::1337:policy/bucketname-readonly',
                         services._policy_arn('bucketname', readwrite=False))
        self.assertEqual('arn:aws:iam::1337:policy/bucketname-readwrite',
                         services._policy_arn('bucketname', readwrite=True))

    def test_bucket_arn(self):
        self.assertEqual('arn:aws:s3:::bucketname', services._bucket_arn('bucketname'))
