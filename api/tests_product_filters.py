from decimal import Decimal

from django.db.models import Q
from django.test import SimpleTestCase

from api.v1.product_filters import apply_product_filters


class _FakeQuerySet:
    def __init__(self):
        self.calls = []

    def _record(self, method, *args, **kwargs):
        self.calls.append((method, args, kwargs))
        return self

    def filter(self, *args, **kwargs):
        return self._record("filter", *args, **kwargs)

    def distinct(self):
        return self._record("distinct")

    def annotate(self, *args, **kwargs):
        return self._record("annotate", *args, **kwargs)

    def select_related(self, *args):
        return self._record("select_related", *args)

    def prefetch_related(self, *args):
        return self._record("prefetch_related", *args)

    def order_by(self, *args):
        return self._record("order_by", *args)


class ProductFiltersTests(SimpleTestCase):
    def _filter_kwargs(self, queryset):
        return [kwargs for method, _args, kwargs in queryset.calls if method == "filter" and kwargs]

    def test_apply_product_filters_defaults_to_active_and_orders_by_name(self):
        queryset = _FakeQuerySet()

        out = apply_product_filters(queryset, {})

        self.assertIs(out, queryset)
        self.assertEqual(queryset.calls[0], ("filter", (), {"is_active": True}))
        self.assertIn(("order_by", ("name",), {}), queryset.calls)
        self.assertIn(("select_related", ("category",), {}), queryset.calls)
        self.assertIn(("prefetch_related", ("tags",), {}), queryset.calls)
        self.assertFalse(any(method == "distinct" for method, _args, _kwargs in queryset.calls))

        annotate_calls = [kwargs for method, _args, kwargs in queryset.calls if method == "annotate"]
        self.assertEqual(len(annotate_calls), 1)
        self.assertIn("available_stock", annotate_calls[0])

    def test_apply_product_filters_applies_every_supported_filter(self):
        queryset = _FakeQuerySet()
        params = {
            "is_active": "0",
            "q": "needle",
            "name": "Bandage",
            "brand": "ACME",
            "sku": "SKU-1",
            "barcode": "123",
            "ean": "987",
            "color": "Blue",
            "category": "Health",
            "category_id": "12",
            "tag": "urgent",
            "tag_id": "7",
            "storage_conditions": "dry",
            "notes": "fragile",
            "perishable": "yes",
            "quarantine_default": "no",
            "default_location_id": "9",
            "pu_ht": "10,50",
            "tva": "0.2",
            "pu_ttc": "12.60",
            "weight_g": "110",
            "volume_cm3": "220",
            "length_cm": "3,5",
            "width_cm": "4.5",
            "height_cm": "5",
            "available_stock": "8",
        }

        out = apply_product_filters(queryset, params)

        self.assertIs(out, queryset)
        self.assertTrue(any(method == "distinct" for method, _args, _kwargs in queryset.calls))
        kwargs_calls = self._filter_kwargs(queryset)
        self.assertIn({"is_active": False}, kwargs_calls)
        self.assertIn({"name__icontains": "Bandage"}, kwargs_calls)
        self.assertIn({"brand__icontains": "ACME"}, kwargs_calls)
        self.assertIn({"sku__icontains": "SKU-1"}, kwargs_calls)
        self.assertIn({"barcode__icontains": "123"}, kwargs_calls)
        self.assertIn({"ean__icontains": "987"}, kwargs_calls)
        self.assertIn({"color__icontains": "Blue"}, kwargs_calls)
        self.assertIn({"category__name__icontains": "Health"}, kwargs_calls)
        self.assertIn({"category_id": 12}, kwargs_calls)
        self.assertIn({"tags__name__icontains": "urgent"}, kwargs_calls)
        self.assertIn({"tags__id": 7}, kwargs_calls)
        self.assertIn({"storage_conditions__icontains": "dry"}, kwargs_calls)
        self.assertIn({"notes__icontains": "fragile"}, kwargs_calls)
        self.assertIn({"perishable": True}, kwargs_calls)
        self.assertIn({"quarantine_default": False}, kwargs_calls)
        self.assertIn({"default_location_id": 9}, kwargs_calls)
        self.assertIn({"pu_ht": Decimal("10.50")}, kwargs_calls)
        self.assertIn({"tva": Decimal("0.2")}, kwargs_calls)
        self.assertIn({"pu_ttc": Decimal("12.60")}, kwargs_calls)
        self.assertIn({"weight_g": 110}, kwargs_calls)
        self.assertIn({"volume_cm3": 220}, kwargs_calls)
        self.assertIn({"length_cm": Decimal("3.5")}, kwargs_calls)
        self.assertIn({"width_cm": Decimal("4.5")}, kwargs_calls)
        self.assertIn({"height_cm": Decimal("5")}, kwargs_calls)
        self.assertIn({"available_stock": 8}, kwargs_calls)

        q_filters = [
            args[0]
            for method, args, kwargs in queryset.calls
            if method == "filter" and args and not kwargs
        ]
        self.assertEqual(len(q_filters), 1)
        self.assertIsInstance(q_filters[0], Q)

    def test_apply_product_filters_ignores_invalid_numeric_and_boolean_values(self):
        queryset = _FakeQuerySet()
        params = {
            "is_active": "maybe",
            "category_id": "abc",
            "tag_id": "xyz",
            "perishable": "unknown",
            "pu_ht": "invalid",
            "available_stock": "not-an-int",
        }

        out = apply_product_filters(queryset, params)

        self.assertIs(out, queryset)
        kwargs_calls = self._filter_kwargs(queryset)
        self.assertIn({"is_active": True}, kwargs_calls)
        self.assertNotIn({"category_id": "abc"}, kwargs_calls)
        self.assertNotIn({"tags__id": "xyz"}, kwargs_calls)
        self.assertFalse(any("available_stock" in call for call in kwargs_calls))
