from unittest.case import TestCase

from control_panel_api import services


class ServicesTestCase(TestCase):
    def test_policy_document_readwrite(self):
        document = services.get_policy_document('foo', readwrite=True)

        sids = [s['Sid'] for s in document['Statement']]
        self.assertIn('UpdateRenameAndDeleteObjects', sids)

        document = services.get_policy_document('foo', readwrite=False)

        sids = [s['Sid'] for s in document['Statement']]
        self.assertNotIn('UpdateRenameAndDeleteObjects', sids)
