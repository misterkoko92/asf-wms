from django.test import TestCase

from wms.billing_calculations import ShipmentUnitInput
from wms.models import ShipmentUnitEquivalenceRule
from wms.unit_equivalence import resolve_shipment_unit_count


class SharedUnitEquivalenceTests(TestCase):
    def test_shared_entry_point_resolves_units_from_rules(self):
        ShipmentUnitEquivalenceRule.objects.create(label="Default x2", units_per_item=2)

        total_units = resolve_shipment_unit_count(
            items=[ShipmentUnitInput(product=None, quantity=3)],
            rules=ShipmentUnitEquivalenceRule.objects.all(),
        )

        self.assertEqual(total_units, 6)
