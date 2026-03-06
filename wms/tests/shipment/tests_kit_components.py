from types import SimpleNamespace

from django.test import SimpleTestCase

from wms.kit_components import KitCycleError, get_component_quantities, get_unit_component_quantities


class _KitItemsManager:
    def __init__(self, items):
        self._items = list(items)

    def select_related(self, *_args):
        return list(self._items)


class _FailingKitItemsManager:
    def select_related(self, *_args):
        raise AssertionError("kit_items.select_related should not be called")


class KitComponentsTests(SimpleTestCase):
    def _make_product(self, product_id, *, items=None, prefetched_items=None):
        product = SimpleNamespace(id=product_id)
        product.kit_items = _KitItemsManager(items or [])
        if prefetched_items is not None:
            product._prefetched_objects_cache = {"kit_items": list(prefetched_items)}
        return product

    def test_get_unit_component_quantities_returns_empty_for_missing_product_id(self):
        self.assertEqual(get_unit_component_quantities(None), {})
        self.assertEqual(get_unit_component_quantities(SimpleNamespace(id=None)), {})

    def test_get_unit_component_quantities_returns_cached_memo_value(self):
        product = SimpleNamespace(id=10, kit_items=_FailingKitItemsManager())

        cached = get_unit_component_quantities(product, _memo={10: {4: 3}})

        self.assertEqual(cached, {4: 3})

    def test_get_unit_component_quantities_raises_cycle_error_with_path(self):
        product_a = self._make_product(1)
        product_b = self._make_product(2)
        product_a.kit_items = _KitItemsManager(
            [SimpleNamespace(component=product_b, quantity=1)]
        )
        product_b.kit_items = _KitItemsManager(
            [SimpleNamespace(component=product_a, quantity=1)]
        )

        with self.assertRaises(KitCycleError) as exc:
            get_unit_component_quantities(product_a)

        self.assertEqual(exc.exception.cycle_ids, [1, 2, 1])
        self.assertIn("1 -> 2 -> 1", str(exc.exception))

    def test_get_component_quantities_returns_empty_for_non_positive_quantity(self):
        product = self._make_product(7)

        self.assertEqual(get_component_quantities(product, quantity=0), {})
        self.assertEqual(get_component_quantities(product, quantity=None), {})

    def test_get_component_quantities_scales_unit_quantities(self):
        component = self._make_product(12)
        kit = self._make_product(
            11,
            prefetched_items=[SimpleNamespace(component=component, quantity=2)],
        )

        quantities = get_component_quantities(kit, quantity=3)

        self.assertEqual(quantities, {12: 6})
