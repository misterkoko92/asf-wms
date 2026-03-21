import tempfile
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from contacts.models import Contact, ContactCapability, ContactCapabilityType, ContactType
from wms.forms import ScanReceiptAssociationForm
from wms.models import (
    Receipt,
    ReceiptType,
    Warehouse,
)
from wms.shipment_party_setup import ensure_shipment_shipper


class AssociationReceiptBillingFieldsTests(TestCase):
    def setUp(self):
        self.media_root = tempfile.TemporaryDirectory()
        self.override = override_settings(MEDIA_ROOT=self.media_root.name)
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.addCleanup(self.media_root.cleanup)

        self.user = get_user_model().objects.create_user(
            username="billing-receipt-user",
            is_staff=True,
        )
        self.client.force_login(self.user)
        self.warehouse = Warehouse.objects.create(name="Reception", code="REC")
        self.source_contact = self._create_contact(
            "Association Billing",
            role="shipper",
        )
        self.carrier_contact = self._create_contact(
            "Transport Billing",
            role=ContactCapabilityType.TRANSPORTER,
        )

    def _create_contact(self, name, *, role=None):
        contact = Contact.objects.create(
            name=name,
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        if role == "shipper":
            ensure_shipment_shipper(contact)
        elif role is not None:
            ContactCapability.objects.create(
                contact=contact,
                capability=role,
                is_active=True,
            )
        return contact

    def test_association_receipt_stores_pickup_billing_fields(self):
        receipt = Receipt.objects.create(
            receipt_type=ReceiptType.ASSOCIATION,
            source_contact=self.source_contact,
            warehouse=self.warehouse,
            pickup_charge_amount=Decimal("35.00"),
            pickup_charge_currency="EUR",
            pickup_charge_comment="Enlevement organise par ASF.",
            pickup_charge_proof=SimpleUploadedFile(
                "pickup-proof.pdf",
                b"%PDF-1.4 pickup",
                content_type="application/pdf",
            ),
        )

        self.assertEqual(receipt.pickup_charge_amount, Decimal("35.00"))
        self.assertEqual(receipt.pickup_charge_currency, "EUR")
        self.assertEqual(receipt.pickup_charge_comment, "Enlevement organise par ASF.")
        self.assertTrue(receipt.pickup_charge_proof)

    def test_scan_receipt_association_form_accepts_pickup_billing_fields(self):
        uploaded = SimpleUploadedFile(
            "pickup-proof.pdf",
            b"%PDF-1.4 pickup",
            content_type="application/pdf",
        )
        form = ScanReceiptAssociationForm(
            data={
                "received_on": "2026-03-07",
                "carton_count": 4,
                "hors_format_count": 0,
                "source_contact": self.source_contact.id,
                "carrier_contact": self.carrier_contact.id,
                "pickup_charge_amount": "35.00",
                "pickup_charge_currency": "CHF",
                "pickup_charge_comment": "Collecte refacturee.",
            },
            files={"pickup_charge_proof": uploaded},
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["pickup_charge_amount"], Decimal("35.00"))
        self.assertEqual(form.cleaned_data["pickup_charge_currency"], "CHF")
        self.assertEqual(form.cleaned_data["pickup_charge_comment"], "Collecte refacturee.")
        self.assertEqual(form.cleaned_data["pickup_charge_proof"].name, "pickup-proof.pdf")

    def test_scan_receive_association_persists_pickup_billing_fields(self):
        uploaded = SimpleUploadedFile(
            "pickup-proof.pdf",
            b"%PDF-1.4 pickup",
            content_type="application/pdf",
        )

        response = self.client.post(
            reverse("scan:scan_receive_association"),
            {
                "received_on": "2026-03-07",
                "carton_count": 3,
                "hors_format_count": 0,
                "source_contact": self.source_contact.id,
                "carrier_contact": self.carrier_contact.id,
                "pickup_charge_amount": "48.50",
                "pickup_charge_currency": "USD",
                "pickup_charge_comment": "Enlevement externe a facturer.",
                "pickup_charge_proof": uploaded,
            },
        )

        self.assertEqual(response.status_code, 302)
        receipt = Receipt.objects.get(receipt_type=ReceiptType.ASSOCIATION)
        self.assertEqual(receipt.pickup_charge_amount, Decimal("48.50"))
        self.assertEqual(receipt.pickup_charge_currency, "USD")
        self.assertEqual(receipt.pickup_charge_comment, "Enlevement externe a facturer.")
        self.assertTrue(receipt.pickup_charge_proof)
