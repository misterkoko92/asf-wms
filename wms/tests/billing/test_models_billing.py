from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from contacts.models import Contact, ContactType
from wms.models import (
    AssociationBillingProfile,
    AssociationProfile,
    BillingDocument,
    BillingDocumentKind,
    BillingDocumentStatus,
    Receipt,
    ReceiptShipmentAllocation,
    ReceiptType,
    Shipment,
    Warehouse,
)


class BillingModelTests(TestCase):
    def _create_association_profile(self, *, username: str = "billing-user") -> AssociationProfile:
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

    def _create_receipt(self) -> Receipt:
        warehouse = Warehouse.objects.create(name="Warehouse Billing", code="WB")
        return Receipt.objects.create(
            receipt_type=ReceiptType.ASSOCIATION,
            warehouse=warehouse,
        )

    def _create_shipment(self) -> Shipment:
        return Shipment.objects.create(
            shipper_name="Association Billing",
            recipient_name="Recipient Billing",
            destination_address="1 rue de la facturation",
        )

    def test_association_profile_creation_creates_billing_profile(self):
        association_profile = self._create_association_profile()

        self.assertTrue(
            AssociationBillingProfile.objects.filter(
                association_profile=association_profile
            ).exists()
        )
        self.assertEqual(
            association_profile.billing_profile.association_profile_id,
            association_profile.id,
        )

    def test_billing_document_defaults_to_draft_status(self):
        association_profile = self._create_association_profile(username="billing-quote")

        document = BillingDocument.objects.create(
            association_profile=association_profile,
            kind=BillingDocumentKind.QUOTE,
        )

        self.assertEqual(document.status, BillingDocumentStatus.DRAFT)
        self.assertTrue(document.quote_number.startswith("DEV-"))

    def test_billing_document_invoice_requires_manual_number(self):
        association_profile = self._create_association_profile(username="billing-invoice")

        document = BillingDocument(
            association_profile=association_profile,
            kind=BillingDocumentKind.INVOICE,
        )

        with self.assertRaises(ValidationError) as exc:
            document.full_clean()
        self.assertIn("invoice_number", exc.exception.message_dict)

    def test_receipt_shipment_allocation_is_unique_per_pair(self):
        receipt = self._create_receipt()
        shipment = self._create_shipment()
        ReceiptShipmentAllocation.objects.create(
            receipt=receipt,
            shipment=shipment,
            allocated_received_units=4,
        )

        duplicate = ReceiptShipmentAllocation(
            receipt=receipt,
            shipment=shipment,
            allocated_received_units=1,
        )

        with self.assertRaises(ValidationError) as exc:
            duplicate.full_clean()
        self.assertIn("__all__", exc.exception.message_dict)
