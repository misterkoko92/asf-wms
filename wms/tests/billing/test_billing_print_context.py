from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from contacts.models import Contact, ContactType
from wms.models import (
    AssociationProfile,
    BillingDocument,
    BillingDocumentKind,
    BillingDocumentLine,
)
from wms.print_context import build_preview_context
from wms.print_pack_mapping_catalog import is_allowed_source_key


class BillingPrintContextTests(TestCase):
    def setUp(self):
        self.association_profile = self._create_association_profile()

    def _create_association_profile(self):
        user = get_user_model().objects.create_user(
            username="billing-print-user",
            email="billing-print-user@example.com",
        )
        contact = Contact.objects.create(
            name="Billing Print Association",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        return AssociationProfile.objects.create(user=user, contact=contact)

    def _create_document(self, *, kind, number_field, number_value):
        create_kwargs = {
            "association_profile": self.association_profile,
            "kind": kind,
            "status": "issued" if kind != BillingDocumentKind.QUOTE else "draft",
            "currency": "EUR",
        }
        if number_field:
            create_kwargs[number_field] = number_value
        document = BillingDocument.objects.create(
            **create_kwargs,
        )
        BillingDocumentLine.objects.create(
            document=document,
            line_number=1,
            label=f"Ligne {kind}",
            description="Service billing",
            quantity=Decimal("1.00"),
            unit_price=Decimal("75.00"),
            total_amount=Decimal("75.00"),
            is_manual=False,
        )
        return document

    def test_build_preview_context_supports_billing_document_types(self):
        cases = (
            ("billing_quote", BillingDocumentKind.QUOTE, "quote_number", "DEV-2026-0001"),
            ("billing_invoice", BillingDocumentKind.INVOICE, "invoice_number", "FAC-2026-001"),
            (
                "billing_credit_note",
                BillingDocumentKind.CREDIT_NOTE,
                "credit_note_number",
                "AV-2026-001",
            ),
        )

        for doc_type, kind, number_field, number_value in cases:
            with self.subTest(doc_type=doc_type):
                document = self._create_document(
                    kind=kind,
                    number_field=number_field,
                    number_value=number_value,
                )
                context = build_preview_context(doc_type, billing_document=document)
                self.assertEqual(context["billing"]["kind"], kind)
                self.assertEqual(context["billing"]["number"], number_value)
                self.assertEqual(context["billing"]["lines"][0]["label"], f"Ligne {kind}")

    def test_build_preview_context_prefers_issued_snapshot_for_billing_documents(self):
        document = self._create_document(
            kind=BillingDocumentKind.INVOICE,
            number_field="invoice_number",
            number_value="FAC-2026-002",
        )
        document.issued_snapshot = {
            "billing_name": "Snapshot Association",
            "billing_address": "10 rue Snapshot",
            "currency": "USD",
            "exchange_rate": "1.100000",
            "total_amount": "120.00",
            "lines": [
                {
                    "line_number": 1,
                    "label": "Snapshot line",
                    "description": "Snapshot description",
                    "quantity": "1.00",
                    "unit_price": "120.00",
                    "total_amount": "120.00",
                }
            ],
            "shipments": [],
        }
        document.save(update_fields=["issued_snapshot", "updated_at"])

        context = build_preview_context("billing_invoice", billing_document=document)

        self.assertEqual(context["billing"]["billing_name"], "Snapshot Association")
        self.assertEqual(context["billing"]["currency"], "USD")
        self.assertEqual(context["billing"]["lines"][0]["label"], "Snapshot line")

    def test_billing_source_keys_are_allowed_for_template_mapping(self):
        self.assertTrue(is_allowed_source_key("billing.kind"))
        self.assertTrue(is_allowed_source_key("billing.number"))
        self.assertTrue(is_allowed_source_key("billing.lines[].label"))
        self.assertTrue(is_allowed_source_key("billing.shipments[].shipment_date"))
