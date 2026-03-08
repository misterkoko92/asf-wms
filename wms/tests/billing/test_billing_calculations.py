from decimal import Decimal

from django.test import TestCase

from wms.billing_calculations import (
    ShipmentUnitInput,
    build_billing_breakdown,
    resolve_shipment_unit_count,
)
from wms.models import (
    BillingBaseUnitSource,
    BillingComputationProfile,
    BillingExtraUnitMode,
    Product,
    ProductCategory,
    ShipmentUnitEquivalenceRule,
)


class BillingCalculationsTests(TestCase):
    def _create_product(self, *, name, category):
        return Product.objects.create(
            name=name,
            category=category,
            qr_code_image="qr_codes/test.png",
        )

    def test_mixed_standard_cartons_default_to_one_unit_each(self):
        category_mm = ProductCategory.objects.create(name="MM")
        category_cn = ProductCategory.objects.create(name="CN")
        items = [
            ShipmentUnitInput(
                product=self._create_product(name="Colis MM", category=category_mm),
                quantity=1,
            ),
            ShipmentUnitInput(
                product=self._create_product(name="Colis CN", category=category_cn),
                quantity=2,
            ),
        ]

        result = resolve_shipment_unit_count(items=items, rules=[])

        self.assertEqual(result, 3)

    def test_hors_format_rule_applies_specific_equivalence(self):
        root = ProductCategory.objects.create(name="Materiel")
        category = ProductCategory.objects.create(name="Fauteuil roulant", parent=root)
        rule = ShipmentUnitEquivalenceRule.objects.create(
            label="Fauteuil hors format",
            category=category,
            applies_to_hors_format=True,
            units_per_item=10,
        )
        items = [
            ShipmentUnitInput(
                product=self._create_product(name="Fauteuil", category=category),
                quantity=2,
                is_hors_format=True,
            )
        ]

        result = resolve_shipment_unit_count(items=items, rules=[rule])

        self.assertEqual(result, 20)

    def test_more_specific_category_rule_beats_parent_rule(self):
        root = ProductCategory.objects.create(name="Materiel medical")
        child = ProductCategory.objects.create(name="Fauteuil roulant", parent=root)
        ShipmentUnitEquivalenceRule.objects.create(
            label="Materiel medical",
            category=root,
            units_per_item=1,
        )
        specific_rule = ShipmentUnitEquivalenceRule.objects.create(
            label="Fauteuil roulant",
            category=child,
            units_per_item=10,
        )
        items = [
            ShipmentUnitInput(
                product=self._create_product(name="Fauteuil enfant", category=child),
                quantity=1,
            )
        ]

        result = resolve_shipment_unit_count(
            items=items, rules=list(ShipmentUnitEquivalenceRule.objects.all())
        )

        self.assertEqual(result, 10)
        self.assertEqual(specific_rule.units_per_item, 10)

    def test_receipt_linked_formula_uses_allocated_received_units(self):
        profile = BillingComputationProfile.objects.create(
            code="receipt-linked",
            label="Receipt linked",
            base_unit_source=BillingBaseUnitSource.ALLOCATED_RECEIVED_UNITS,
            base_step_size=10,
            base_step_price=Decimal("75.00"),
            extra_unit_mode=BillingExtraUnitMode.SHIPPED_MINUS_ALLOCATED_RECEIVED,
            extra_unit_price=Decimal("10.00"),
        )

        result = build_billing_breakdown(
            profile=profile,
            shipped_units=14,
            allocated_received_units=10,
        )

        self.assertEqual(result.base_amount, Decimal("75.00"))
        self.assertEqual(result.extra_amount, Decimal("40.00"))
        self.assertEqual(result.total_amount, Decimal("115.00"))

    def test_manual_override_hooks_replace_computed_units_when_allowed(self):
        profile = BillingComputationProfile.objects.create(
            code="manual-override",
            label="Manual override",
            base_unit_source=BillingBaseUnitSource.SHIPPED_UNITS,
            base_step_size=10,
            base_step_price=Decimal("75.00"),
            extra_unit_mode=BillingExtraUnitMode.SHIPPED_MINUS_ALLOCATED_RECEIVED,
            extra_unit_price=Decimal("10.00"),
            allow_manual_override=True,
        )

        result = build_billing_breakdown(
            profile=profile,
            shipped_units=22,
            allocated_received_units=10,
            manual_base_units=5,
            manual_extra_units=2,
        )

        self.assertEqual(result.base_amount, Decimal("75.00"))
        self.assertEqual(result.extra_amount, Decimal("20.00"))
        self.assertEqual(result.total_amount, Decimal("95.00"))
        self.assertTrue(result.used_manual_override)
