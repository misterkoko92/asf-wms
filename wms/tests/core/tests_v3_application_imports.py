from django.test import SimpleTestCase

from wms import policies
from wms.application import pilotage, planning, portal, scan


class V31ApplicationImportsTests(SimpleTestCase):
    def test_v31_packages_import(self):
        self.assertIsNotNone(scan)
        self.assertIsNotNone(pilotage)
        self.assertIsNotNone(portal)
        self.assertIsNotNone(planning)
        self.assertIsNotNone(policies)
