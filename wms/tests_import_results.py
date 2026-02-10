from django.test import SimpleTestCase

from wms.import_results import normalize_import_result


class ImportResultsTests(SimpleTestCase):
    def test_normalize_import_result_returns_four_values_unchanged(self):
        result = (1, 2, ["e1"], ["w1"])
        self.assertEqual(normalize_import_result(result), result)

    def test_normalize_import_result_adds_empty_warnings_for_three_values(self):
        self.assertEqual(normalize_import_result((3, 4, ["e2"])), (3, 4, ["e2"], []))
