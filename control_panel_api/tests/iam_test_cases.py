from unittest.case import TestCase


class IAMPolicyTestCase(TestCase):

    def assert_allowed(self, document, action, resource):
        statements = document['Statement']
        for statement in statements:
            actions = statement['Action']
            resources = statement['Resource']
            if action in actions and resource in resources:
                return True

        raise AssertionError(f'Expected policy to allow "{action}" on "{resource}"')

    def assert_not_allowed(self, document, action, resource):
        try:
            self.assert_allowed(document, action, resource)
        except AssertionError:
            pass
        else:
            raise AssertionError(f'Expected policy to not allow "{action}" on "{resource}"')

    def assert_has_sid(self, document, sid):
        statements = document['Statement']
        for statement in statements:
            if statement['Sid'] == sid:
                return True

        raise AssertionError(f'Sid "{sid}" not found in {statements}')

    def assert_has_not_sid(self, document, sid):
        try:
            self.assert_has_sid(document, sid)
            raise AssertionError(f'Sid "{sid}" found in {statements}')
        except AssertionError:
            pass
