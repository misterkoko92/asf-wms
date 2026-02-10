from decimal import Decimal

from django.test import SimpleTestCase

from wms.scan_parse import parse_decimal, parse_int


class ScanParseTests(SimpleTestCase):
    def test_parse_decimal_accepts_comma(self):
        self.assertEqual(parse_decimal("12,5"), Decimal("12.5"))

    def test_parse_decimal_handles_invalid(self):
        self.assertIsNone(parse_decimal("x"))
        self.assertIsNone(parse_decimal(""))

    def test_parse_int_handles_invalid(self):
        self.assertEqual(parse_int("12"), 12)
        self.assertIsNone(parse_int("x"))
        self.assertIsNone(parse_int(""))
