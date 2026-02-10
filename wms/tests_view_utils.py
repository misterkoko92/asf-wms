from unittest import mock

from django.test import SimpleTestCase

from wms.view_utils import resolve_contact_by_name, sorted_choices


class ViewUtilsTests(SimpleTestCase):
    def test_resolve_contact_by_name_returns_none_for_empty_name(self):
        self.assertIsNone(resolve_contact_by_name(("tag",), ""))
        self.assertIsNone(resolve_contact_by_name(("tag",), None))

    def test_resolve_contact_by_name_filters_case_insensitive(self):
        expected = object()
        queryset = mock.MagicMock()
        queryset.filter.return_value.first.return_value = expected

        with mock.patch("wms.view_utils.contacts_with_tags", return_value=queryset):
            result = resolve_contact_by_name(("tag",), "Alice")

        self.assertIs(result, expected)
        queryset.filter.assert_called_once_with(name__iexact="Alice")

    def test_sorted_choices_orders_by_label_case_insensitive(self):
        choices = [("b", "Zulu"), ("c", ""), ("a", "alpha")]
        self.assertEqual(sorted_choices(choices), [("c", ""), ("a", "alpha"), ("b", "Zulu")])
