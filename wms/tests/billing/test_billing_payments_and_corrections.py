from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from contacts.models import Contact, ContactType
from wms.billing_document_handlers import (
    create_credit_note_for_invoice,
    create_replacement_invoice_from_invoice,
    record_billing_payment,
)
from wms.models import (
    AssociationProfile,
    BillingDocument,
    BillingDocumentCorrectionState,
    BillingDocumentKind,
    BillingDocumentLine,
    BillingDocumentShipment,
    BillingDocumentStatus,
    BillingIssue,
    BillingPaymentMethod,
    Shipment,
    ShipmentStatus,
)


class BillingPaymentsAndCorrectionsTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="billing-corrections-user",
            email="billing-corrections-user@example.com",
        )
        association_contact = Contact.objects.create(
            name="Association Billing Corrections",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        self.association_profile = AssociationProfile.objects.create(
            user=self.user,
            contact=association_contact,
        )

    def _create_shipment(self, *, reference):
        return Shipment.objects.create(
            reference=reference,
            status=ShipmentStatus.SHIPPED,
            shipper_name=self.association_profile.contact.name,
            shipper_contact_ref=self.association_profile.contact,
            recipient_name="Recipient",
            destination_address="1 rue du test",
            ready_at=timezone.now(),
        )

    def _create_issued_invoice(self, *, reference="EXP-PAY-001"):
        shipment = self._create_shipment(reference=reference)
        invoice = BillingDocument.objects.create(
            association_profile=self.association_profile,
            kind=BillingDocumentKind.INVOICE,
            status=BillingDocumentStatus.ISSUED,
            invoice_number="FAC-2026-900",
            currency="EUR",
            exchange_rate=Decimal("1.000000"),
            issued_at=timezone.now(),
        )
        BillingDocumentShipment.objects.create(document=invoice, shipment=shipment)
        BillingDocumentLine.objects.create(
            document=invoice,
            line_number=1,
            label="Expedition facturee",
            description="Reference facturee",
            quantity=Decimal("1.00"),
            unit_price=Decimal("75.00"),
            total_amount=Decimal("75.00"),
            is_manual=False,
        )
        return invoice

    def test_invoice_becomes_partially_paid_after_first_payment(self):
        invoice = self._create_issued_invoice()

        record_billing_payment(
            document=invoice,
            amount=Decimal("20.00"),
            payment_method=BillingPaymentMethod.BANK_TRANSFER,
            created_by=self.user,
        )
        invoice.refresh_from_db()

        self.assertEqual(invoice.status, BillingDocumentStatus.PARTIALLY_PAID)

    def test_invoice_becomes_paid_when_cumulative_payments_cover_total(self):
        invoice = self._create_issued_invoice(reference="EXP-PAY-002")

        record_billing_payment(
            document=invoice,
            amount=Decimal("20.00"),
            payment_method=BillingPaymentMethod.BANK_TRANSFER,
            created_by=self.user,
        )
        record_billing_payment(
            document=invoice,
            amount=Decimal("55.00"),
            payment_method=BillingPaymentMethod.CHECK,
            created_by=self.user,
        )
        invoice.refresh_from_db()

        self.assertEqual(invoice.status, BillingDocumentStatus.PAID)

    def test_open_billing_issue_moves_invoice_into_review_state(self):
        invoice = self._create_issued_invoice(reference="EXP-ISSUE-001")

        BillingIssue.objects.create(
            document=invoice,
            description="Le document doit etre revu.",
            reported_by=self.user,
        )
        invoice.refresh_from_db()

        self.assertEqual(
            invoice.correction_state,
            BillingDocumentCorrectionState.IN_REVIEW,
        )

    def test_create_credit_note_marks_invoice_corrected_and_links_original(self):
        invoice = self._create_issued_invoice(reference="EXP-CREDIT-001")

        credit_note = create_credit_note_for_invoice(
            document=invoice,
            credit_note_number="AV-2026-001",
            created_by=self.user,
        )
        invoice.refresh_from_db()

        self.assertEqual(invoice.status, BillingDocumentStatus.CANCELLED_OR_CORRECTED)
        self.assertEqual(credit_note.kind, BillingDocumentKind.CREDIT_NOTE)
        self.assertEqual(credit_note.status, BillingDocumentStatus.ISSUED)
        self.assertEqual(credit_note.parent_document, invoice)
        self.assertEqual(credit_note.lines.get().total_amount, Decimal("-75.00"))

    def test_create_replacement_invoice_preserves_original_audit_trail(self):
        invoice = self._create_issued_invoice(reference="EXP-REPLACE-001")
        create_credit_note_for_invoice(
            document=invoice,
            credit_note_number="AV-2026-002",
            created_by=self.user,
        )

        replacement_invoice = create_replacement_invoice_from_invoice(
            document=invoice,
            created_by=self.user,
        )

        self.assertEqual(replacement_invoice.kind, BillingDocumentKind.INVOICE)
        self.assertEqual(replacement_invoice.status, BillingDocumentStatus.DRAFT)
        self.assertEqual(replacement_invoice.parent_document, invoice)
        self.assertIsNone(replacement_invoice.invoice_number)
        self.assertEqual(
            list(
                replacement_invoice.shipment_links.order_by("shipment_id").values_list(
                    "shipment_id",
                    flat=True,
                )
            ),
            list(
                invoice.shipment_links.order_by("shipment_id").values_list("shipment_id", flat=True)
            ),
        )
