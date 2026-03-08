from decimal import Decimal

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from contacts.models import Contact, ContactType
from wms import models


class BillingAdminTests(TestCase):
    def setUp(self):
        self.superuser = get_user_model().objects.create_superuser(
            username="billing-admin",
            email="billing-admin@example.com",
        )
        self.client.force_login(self.superuser)
        association_contact = Contact.objects.create(
            name="Association Admin Billing",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        self.association_profile = models.AssociationProfile.objects.create(
            user=get_user_model().objects.create_user(
                username="billing-admin-association",
                email="billing-admin-association@example.com",
            ),
            contact=association_contact,
        )
        self.shipment = models.Shipment.objects.create(
            reference="EXP-ADMIN-BILL-001",
            status=models.ShipmentStatus.SHIPPED,
            shipper_name=association_contact.name,
            shipper_contact_ref=association_contact,
            recipient_name="Recipient",
            destination_address="1 rue Admin",
            ready_at=timezone.now(),
        )
        self.invoice = models.BillingDocument.objects.create(
            association_profile=self.association_profile,
            kind=models.BillingDocumentKind.INVOICE,
            status=models.BillingDocumentStatus.ISSUED,
            invoice_number="FAC-ADMIN-001",
            currency="EUR",
            issued_at=timezone.now(),
        )
        models.BillingDocumentShipment.objects.create(
            document=self.invoice,
            shipment=self.shipment,
        )
        models.BillingDocumentLine.objects.create(
            document=self.invoice,
            line_number=1,
            label="Ligne admin",
            description="Description admin",
            quantity=Decimal("1.00"),
            unit_price=Decimal("75.00"),
            total_amount=Decimal("75.00"),
        )
        self.payment = models.BillingPayment.objects.create(
            document=self.invoice,
            amount=Decimal("20.00"),
            currency="EUR",
            payment_method=models.BillingPaymentMethod.BANK_TRANSFER,
            reference="PAY-ADMIN-001",
            created_by=self.superuser,
        )
        warehouse = models.Warehouse.objects.create(name="Admin Warehouse", code="AW")
        self.receipt = models.Receipt.objects.create(
            receipt_type=models.ReceiptType.ASSOCIATION,
            source_contact=association_contact,
            carton_count=5,
            warehouse=warehouse,
        )
        self.allocation = models.ReceiptShipmentAllocation.objects.create(
            receipt=self.receipt,
            shipment=self.shipment,
            allocated_received_units=5,
            created_by=self.superuser,
        )

    def test_billing_document_admin_changelist_loads(self):
        response = self.client.get(reverse("admin:wms_billingdocument_changelist"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "FAC-ADMIN-001")
        self.assertContains(response, "Association Admin Billing")

    def test_billing_payment_admin_changelist_loads(self):
        response = self.client.get(reverse("admin:wms_billingpayment_changelist"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "PAY-ADMIN-001")
        self.assertContains(response, "EUR")
        self.assertContains(response, "FAC-ADMIN-001")

    def test_billing_admin_registrations_expose_useful_lists_and_search(self):
        billing_document_admin = admin.site._registry[models.BillingDocument]
        self.assertIn("kind", billing_document_admin.list_display)
        self.assertIn("status", billing_document_admin.list_display)
        self.assertIn("association_profile", billing_document_admin.list_display)
        self.assertIn("invoice_number", billing_document_admin.search_fields)
        self.assertIn("association_profile__contact__name", billing_document_admin.search_fields)

        billing_payment_admin = admin.site._registry[models.BillingPayment]
        self.assertIn("document", billing_payment_admin.list_display)
        self.assertIn("amount", billing_payment_admin.list_display)
        self.assertIn("reference", billing_payment_admin.search_fields)

        allocation_admin = admin.site._registry[models.ReceiptShipmentAllocation]
        self.assertIn("receipt", allocation_admin.list_display)
        self.assertIn("shipment", allocation_admin.list_display)

        profile_admin = admin.site._registry[models.AssociationBillingProfile]
        self.assertIn("association_profile", profile_admin.list_display)
        self.assertIn("billing_frequency", profile_admin.list_display)
