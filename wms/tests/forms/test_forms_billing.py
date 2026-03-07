from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from contacts.models import Contact, ContactType
from wms.forms_billing import (
    BillingAssociationPriceOverrideForm,
    BillingComputationProfileForm,
)
from wms.models import (
    AssociationProfile,
    BillingAssociationPriceOverride,
    BillingBaseUnitSource,
    BillingComputationProfile,
    BillingExtraUnitMode,
    BillingServiceCatalogItem,
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
