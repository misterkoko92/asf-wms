from datetime import date, datetime, time
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from contacts.models import Contact, ContactType
from wms.billing_document_handlers import (
    build_editor_candidates,
    create_billing_draft,
    issue_billing_document,
)
from wms.models import (
    AssociationProfile,
    BillingComputationProfile,
    BillingDocument,
    BillingDocumentKind,
    BillingDocumentShipment,
    BillingDocumentStatus,
    BillingExtraUnitMode,
    Receipt,
    ReceiptShipmentAllocation,
    ReceiptType,
    Shipment,
    ShipmentStatus,
    Warehouse,
)


class BillingDocumentHandlersTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="billing-document-user",
            email="billing-document-user@example.com",
        )
        self.warehouse = Warehouse.objects.create(name="Billing Documents", code="BD")
        self.association_profile = self._create_association_profile(
            username="billing-doc-association"
        )
        self.computation_profile = BillingComputationProfile.objects.create(
            code="shipment-standard",
            label="Shipment standard",
            base_step_size=10,
            base_step_price=Decimal("75.00"),
            extra_unit_mode=BillingExtraUnitMode.NONE,
            extra_unit_price=Decimal("0.00"),
            is_default_for_shipment_only=True,
        )
        billing_profile = self.association_profile.billing_profile
        billing_profile.default_computation_profile = self.computation_profile
        billing_profile.save(update_fields=["default_computation_profile", "updated_at"])

    def _create_association_profile(self, *, username):
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

    def _create_shipment(
        self, *, association_profile, reference, when, status=ShipmentStatus.SHIPPED
    ):
        shipment = Shipment.objects.create(
            reference=reference,
            status=status,
            shipper_name=association_profile.contact.name,
            shipper_contact_ref=association_profile.contact,
            recipient_name="Recipient",
            destination_address="1 rue de la facturation",
            ready_at=timezone.make_aware(datetime.combine(when, time(10, 0))),
        )
        Shipment.objects.filter(pk=shipment.pk).update(
            created_at=timezone.make_aware(datetime.combine(when, time(9, 0))),
        )
        shipment.refresh_from_db()
        return shipment

    def _create_receipt(self, *, association_profile, carton_count):
        return Receipt.objects.create(
            receipt_type=ReceiptType.ASSOCIATION,
            source_contact=association_profile.contact,
            carton_count=carton_count,
            warehouse=self.warehouse,
        )

    def test_build_editor_candidates_returns_shipped_shipments_for_quote(self):
        january_shipment = self._create_shipment(
            association_profile=self.association_profile,
            reference="EXP-BILL-01",
            when=date(2026, 1, 15),
        )
        self._create_shipment(
            association_profile=self.association_profile,
            reference="EXP-BILL-DRAFT",
            when=date(2026, 1, 20),
            status=ShipmentStatus.DRAFT,
        )

        rows = build_editor_candidates(
            association_profile=self.association_profile,
            kind=BillingDocumentKind.QUOTE,
        )

        self.assertEqual([row.reference for row in rows], [january_shipment.reference])

    def test_editor_excludes_shipments_already_invoiced(self):
        already_invoiced_shipment = self._create_shipment(
            association_profile=self.association_profile,
            reference="EXP-BILL-02",
            when=date(2026, 2, 10),
        )
        invoice = BillingDocument.objects.create(
            association_profile=self.association_profile,
            kind=BillingDocumentKind.INVOICE,
            status=BillingDocumentStatus.ISSUED,
            invoice_number="FAC-2026-001",
            issued_at=timezone.now(),
        )
        BillingDocumentShipment.objects.create(
            document=invoice,
            shipment=already_invoiced_shipment,
        )

        rows = build_editor_candidates(
            association_profile=self.association_profile,
            kind=BillingDocumentKind.INVOICE,
        )

        self.assertNotIn(
            already_invoiced_shipment.id,
            [row.shipment_id for row in rows],
        )

    def test_build_editor_candidates_filters_by_period(self):
        q1_shipment = self._create_shipment(
            association_profile=self.association_profile,
            reference="EXP-BILL-Q1",
            when=date(2026, 3, 1),
        )
        self._create_shipment(
            association_profile=self.association_profile,
            reference="EXP-BILL-Q2",
            when=date(2026, 4, 12),
        )

        rows = build_editor_candidates(
            association_profile=self.association_profile,
            kind=BillingDocumentKind.QUOTE,
            period=(date(2026, 1, 1), date(2026, 3, 31)),
        )

        self.assertEqual([row.reference for row in rows], [q1_shipment.reference])

    def test_create_billing_draft_builds_quote_from_selected_shipments(self):
        shipment = self._create_shipment(
            association_profile=self.association_profile,
            reference="EXP-BILL-03",
            when=date(2026, 1, 25),
        )
        receipt = self._create_receipt(
            association_profile=self.association_profile,
            carton_count=7,
        )
        ReceiptShipmentAllocation.objects.create(
            receipt=receipt,
            shipment=shipment,
            allocated_received_units=7,
            created_by=self.user,
        )

        document = create_billing_draft(
            association_profile=self.association_profile,
            kind=BillingDocumentKind.QUOTE,
            shipment_ids=[shipment.id],
            created_by=self.user,
        )

        self.assertEqual(document.kind, BillingDocumentKind.QUOTE)
        self.assertEqual(document.shipment_links.count(), 1)
        self.assertEqual(document.receipt_links.count(), 1)
        self.assertEqual(document.lines.count(), 1)
        self.assertEqual(document.lines.get().label, "Expedition EXP-BILL-03")

    def test_create_billing_draft_builds_invoice_without_manual_number(self):
        shipment = self._create_shipment(
            association_profile=self.association_profile,
            reference="EXP-BILL-04",
            when=date(2026, 2, 5),
        )

        document = create_billing_draft(
            association_profile=self.association_profile,
            kind=BillingDocumentKind.INVOICE,
            shipment_ids=[shipment.id],
            created_by=self.user,
        )

        self.assertEqual(document.kind, BillingDocumentKind.INVOICE)
        self.assertFalse(document.invoice_number)
        self.assertEqual(document.status, BillingDocumentStatus.DRAFT)

    def test_issue_billing_document_requires_manual_invoice_number(self):
        shipment = self._create_shipment(
            association_profile=self.association_profile,
            reference="EXP-BILL-05",
            when=date(2026, 2, 6),
        )
        document = create_billing_draft(
            association_profile=self.association_profile,
            kind=BillingDocumentKind.INVOICE,
            shipment_ids=[shipment.id],
            created_by=self.user,
        )

        with self.assertRaisesMessage(ValueError, "Invoice number is required before issue."):
            issue_billing_document(document=document)

    def test_issue_billing_document_freezes_snapshot_for_issued_invoice(self):
        shipment = self._create_shipment(
            association_profile=self.association_profile,
            reference="EXP-BILL-06",
            when=date(2026, 2, 7),
        )
        billing_profile = self.association_profile.billing_profile
        billing_profile.billing_name_override = "Association Billing Snapshot"
        billing_profile.billing_address_override = "10 rue du Snapshot\n75001 Paris"
        billing_profile.save(
            update_fields=[
                "billing_name_override",
                "billing_address_override",
                "updated_at",
            ]
        )
        document = create_billing_draft(
            association_profile=self.association_profile,
            kind=BillingDocumentKind.INVOICE,
            shipment_ids=[shipment.id],
            created_by=self.user,
        )
        document.exchange_rate = Decimal("1.234500")
        document.save(update_fields=["exchange_rate", "updated_at"])

        issued_document = issue_billing_document(
            document=document,
            invoice_number="FAC-2026-001",
        )

        self.assertEqual(issued_document.status, BillingDocumentStatus.ISSUED)
        self.assertEqual(issued_document.invoice_number, "FAC-2026-001")
        self.assertIsNotNone(issued_document.issued_at)
        self.assertEqual(
            issued_document.issued_snapshot["billing_name"],
            "Association Billing Snapshot",
        )
        self.assertEqual(
            issued_document.issued_snapshot["billing_address"],
            "10 rue du Snapshot\n75001 Paris",
        )
        self.assertEqual(issued_document.issued_snapshot["currency"], issued_document.currency)
        self.assertEqual(
            issued_document.issued_snapshot["exchange_rate"],
            "1.234500",
        )
        self.assertEqual(
            issued_document.issued_snapshot["total_amount"],
            str(issued_document.lines.get().total_amount),
        )
        self.assertEqual(
            issued_document.issued_snapshot["lines"][0]["label"],
            issued_document.lines.get().label,
        )
