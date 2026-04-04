from django.test import SimpleTestCase

from wms.view_utils import sorted_choices


class ViewUtilsTests(SimpleTestCase):
    def test_sorted_choices_orders_by_label_case_insensitive(self):
        choices = [("b", "Zulu"), ("c", ""), ("a", "alpha")]
        self.assertEqual(sorted_choices(choices), [("c", ""), ("a", "alpha"), ("b", "Zulu")])

    def test_sorted_choices_keeps_placeholder_first_and_sorts_grouped_choices(self):
        choices = [
            ("", "---------"),
            ("Destinations disponibles", (("b", "Zulu"), ("a", "alpha"))),
            ("Autres destinations", (("d", "delta"), ("c", "Charlie"))),
        ]

        self.assertEqual(
            sorted_choices(choices),
            [
                ("", "---------"),
                ("Destinations disponibles", (("a", "alpha"), ("b", "Zulu"))),
                ("Autres destinations", (("c", "Charlie"), ("d", "delta"))),
            ],
        )

    def test_sorted_choices_supports_descending_order(self):
        choices = [("a", "alpha"), ("c", "Charlie"), ("b", "Zulu")]

        self.assertEqual(
            sorted_choices(choices, order="desc"),
            [("b", "Zulu"), ("c", "Charlie"), ("a", "alpha")],
        )
