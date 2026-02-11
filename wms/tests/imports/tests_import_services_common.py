from django.test import SimpleTestCase

from wms.import_services_common import _row_is_empty


class ImportServicesCommonTests(SimpleTestCase):
    def test_row_is_empty_ignorés_none_values(self):
        self.assertTrue(_row_is_empty({"a": None, "b": "   "}))
        self.assertFalse(_row_is_empty({"a": None, "b": "x"}))
