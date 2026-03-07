from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from contacts.models import Contact, ContactType
from wms.forms_billing import (
    BillingAssociationPriceOverrideForm,
    BillingComputationProfileForm,
    ShipmentUnitEquivalenceRuleForm,
)
from wms.models import (
    AssociationProfile,
    BillingAssociationPriceOverride,
    BillingBaseUnitSource,
    BillingComputationProfile,
    BillingExtraUnitMode,
    BillingServiceCatalogItem,
    ProductCategory,
    ShipmentUnitEquivalenceRule,
)


class BillingFormsTests(TestCase):
    def _create_association_profile(
        self, *, username: str = "billing-form-user"
    ) -> AssociationProfile:
        user = get_user_model().objects.create_user(
            username=username,
            email=f"{username}@example.com",
        )
        contact = Contact.objects.create(
            name=f"Association {username}",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        return AssociationProfile.objects.create(user=user, contact=contact)

    def test_computation_profile_form_generates_code_from_label(self):
        form = BillingComputationProfileForm(
            data={
                "label": "Receipt linked standard",
                "applies_when_receipts_linked": "True",
                "base_unit_source": BillingBaseUnitSource.ALLOCATED_RECEIVED_UNITS,
                "base_step_size": 10,
                "base_step_price": "75.00",
                "extra_unit_mode": BillingExtraUnitMode.SHIPPED_MINUS_ALLOCATED_RECEIVED,
                "extra_unit_price": "10.00",
                "allow_manual_override": "on",
                "is_default_for_receipt_linked": "on",
                "is_active": "on",
            }
        )

        self.assertTrue(form.is_valid(), form.errors)
        profile = form.save()

        self.assertEqual(profile.code, "receipt-linked-standard")
        self.assertEqual(profile.base_step_price, Decimal("75.00"))

    def test_computation_profile_form_keeps_existing_code_on_edit(self):
        profile = BillingComputationProfile.objects.create(
            code="shipment-standard",
            label="Shipment Standard",
        )
        form = BillingComputationProfileForm(
            data={
                "label": "Shipment standard updated",
                "applies_when_receipts_linked": "",
                "base_unit_source": BillingBaseUnitSource.SHIPPED_UNITS,
                "base_step_size": 20,
                "base_step_price": "150.00",
                "extra_unit_mode": BillingExtraUnitMode.NONE,
                "extra_unit_price": "0.00",
                "allow_manual_override": "",
                "is_default_for_shipment_only": "on",
                "is_active": "on",
            },
            instance=profile,
        )

        self.assertTrue(form.is_valid(), form.errors)
        updated_profile = form.save()

        self.assertEqual(updated_profile.code, "shipment-standard")
        self.assertEqual(updated_profile.base_step_size, 20)

    def test_price_override_form_maps_association_profile_to_billing_profile(self):
        association_profile = self._create_association_profile()
        service = BillingServiceCatalogItem.objects.create(
            label="Export declaration",
            default_unit_price=Decimal("45.00"),
        )
        form = BillingAssociationPriceOverrideForm(
            data={
                "association_profile": association_profile.id,
                "service_catalog_item": service.id,
                "computation_profile": "",
                "overridden_amount": "40.00",
                "currency": "EUR",
                "notes": "Association agreement",
            }
        )

        self.assertTrue(form.is_valid(), form.errors)
        override = form.save()

        self.assertEqual(
            override.association_billing_profile_id,
            association_profile.billing_profile.id,
        )
        self.assertEqual(override.service_catalog_item_id, service.id)

    def test_price_override_form_requires_exactly_one_target(self):
        association_profile = self._create_association_profile(username="billing-form-target")
        service = BillingServiceCatalogItem.objects.create(
            label="Pickup", default_unit_price="30.00"
        )
        computation_profile = BillingComputationProfile.objects.create(
            code="receipt-linked",
            label="Receipt linked",
        )

        form = BillingAssociationPriceOverrideForm(
            data={
                "association_profile": association_profile.id,
                "service_catalog_item": service.id,
                "computation_profile": computation_profile.id,
                "overridden_amount": "20.00",
                "currency": "EUR",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("__all__", form.errors)
        self.assertFalse(BillingAssociationPriceOverride.objects.exists())

    def test_equivalence_rule_form_creates_category_specific_rule(self):
        root_category = ProductCategory.objects.create(name="MM")
        leaf_category = ProductCategory.objects.create(
            name="Wheelchair",
            parent=root_category,
        )
        form = ShipmentUnitEquivalenceRuleForm(
            data={
                "label": "Wheelchair x10",
                "category": leaf_category.id,
                "applies_to_hors_format": "",
                "units_per_item": 10,
                "priority": 1,
                "is_active": "on",
                "notes": "Specific for wheelchairs",
            }
        )

        self.assertTrue(form.is_valid(), form.errors)
        rule = form.save()

        self.assertEqual(rule.category_id, leaf_category.id)
        self.assertEqual(rule.units_per_item, 10)

    def test_equivalence_rule_form_updates_hors_format_rule(self):
        rule = ShipmentUnitEquivalenceRule.objects.create(
            label="Hors format",
            applies_to_hors_format=True,
            units_per_item=4,
            priority=5,
        )
        form = ShipmentUnitEquivalenceRuleForm(
            data={
                "label": "Hors format x6",
                "category": "",
                "applies_to_hors_format": "on",
                "units_per_item": 6,
                "priority": 2,
                "is_active": "on",
                "notes": "Updated rule",
            },
            instance=rule,
        )

        self.assertTrue(form.is_valid(), form.errors)
        updated_rule = form.save()

        self.assertTrue(updated_rule.applies_to_hors_format)
        self.assertEqual(updated_rule.units_per_item, 6)
