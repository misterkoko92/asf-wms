from decimal import Decimal

from django.test import SimpleTestCase

from api.v1.query_utils import parse_bool, parse_decimal, parse_int


class QueryUtilsTests(SimpleTestCase):
    def test_parse_bool(self):
        self.assertIsNone(parse_bool(None))
        self.assertTrue(parse_bool("oui"))
        self.assertTrue(parse_bool("1"))
        self.assertFalse(parse_bool("non"))
        self.assertFalse(parse_bool("0"))
        self.assertIsNone(parse_bool("maybe"))

    def test_parse_int(self):
        self.assertIsNone(parse_int(None))
        self.assertEqual(parse_int("12"), 12)
        self.assertEqual(parse_int(4), 4)
        self.assertIsNone(parse_int("x"))

    def test_parse_decimal(self):
        class _BadDecimalInput:
            def __str__(self):
                raise ArithmeticError("bad")

        self.assertIsNone(parse_decimal(None))
        self.assertEqual(parse_decimal("12.5"), Decimal("12.5"))
        self.assertEqual(parse_decimal("12,5"), Decimal("12.5"))
        self.assertIsNone(parse_decimal(_BadDecimalInput()))
        self.assertIsNone(parse_decimal("x"))
