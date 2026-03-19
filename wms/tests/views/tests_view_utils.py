from django.test import SimpleTestCase

from wms.view_utils import sorted_choices


class ViewUtilsTests(SimpleTestCase):
    def test_sorted_choices_orders_by_label_case_insensitive(self):
        choices = [("b", "Zulu"), ("c", ""), ("a", "alpha")]
        self.assertEqual(sorted_choices(choices), [("c", ""), ("a", "alpha"), ("b", "Zulu")])
