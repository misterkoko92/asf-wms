from datetime import timedelta
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.utils import timezone

from contacts.models import Contact, ContactType
from wms.models import (
    AccountDocument,
    AssociationRecipient,
    Carton,
    CartonStatus,
    Destination,
    DocumentScanStatus,
    Location,
    Order,
    OrderLine,
    Product,
    ProductLot,
    Shipment,
    ShipmentStatus,
    ShipmentTrackingAccessGrant,
    ShipmentTrackingAccessRole,
    Warehouse,
)


class CheckReferentialIntegrityCommandTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="integrity-user",
            email="integrity@example.com",
            password="pass1234",  # pragma: allowlist secret
        )
        self.shipper = Contact.objects.create(
            name="Integrity Shipper",
            contact_type=ContactType.ORGANIZATION,
            email="shipper@example.com",
            is_active=True,
        )
        self.recipient = Contact.objects.create(
            name="Integrity Recipient",
            contact_type=ContactType.ORGANIZATION,
            email="recipient@example.com",
            is_active=True,
        )
        self.correspondent = Contact.objects.create(
            name="Integrity Correspondent",
            contact_type=ContactType.PERSON,
            email="correspondent@example.com",
            is_active=True,
        )
        self.destination = Destination.objects.create(
            city="Integrity City",
            iata_code="INT",
            country="France",
            correspondent_contact=self.correspondent,
            is_active=True,
        )
        warehouse = Warehouse.objects.create(name="Integrity Warehouse", code="INT")
        self.location = Location.objects.create(
            warehouse=warehouse,
            zone="A",
            aisle="1",
            shelf="1",
        )
        self.product = Product.objects.create(name="Integrity Product")

    def _create_valid_shipment(self):
        return Shipment.objects.create(
            status=ShipmentStatus.PACKED,
            shipper_name=self.shipper.name,
            shipper_contact_ref=self.shipper,
            recipient_name=self.recipient.name,
            recipient_contact_ref=self.recipient,
            correspondent_name=self.correspondent.name,
            correspondent_contact_ref=self.correspondent,
            destination=self.destination,
            destination_address="1 rue Integrity",
            destination_country="France",
            created_by=self.user,
        )

    def test_command_passes_when_no_issue_is_detected(self):
        self._create_valid_shipment()
        out = StringIO()

        call_command("check_referential_integrity", stdout=out)

        self.assertIn("Referential integrity: OK", out.getvalue())

    def test_command_reports_representative_issue_families_in_report_only_mode(self):
        invalid_status_shipment = self._create_valid_shipment()
        Shipment.objects.filter(pk=invalid_status_shipment.pk).update(status="unknown")
        Shipment.objects.create(
            status=ShipmentStatus.PACKED,
            shipper_name=self.shipper.name,
            shipper_contact_ref=self.shipper,
            recipient_name=self.recipient.name,
            recipient_contact_ref=self.recipient,
            destination=None,
            destination_address="Missing destination",
            destination_country="France",
            created_by=self.user,
        )
        Carton.objects.create(code="CART-ORPHAN", status=CartonStatus.SHIPPED)
        ProductLot.objects.create(
            product=self.product,
            location=self.location,
            quantity_on_hand=2,
            quantity_reserved=5,
        )
        order = Order.objects.create(
            shipper_name=self.shipper.name,
            recipient_name=self.recipient.name,
            shipper_contact=self.shipper,
            recipient_contact=self.recipient,
            destination_address="1 rue Integrity",
            destination_city="Integrity City",
            destination_country="France",
            created_by=self.user,
        )
        OrderLine.objects.create(order=order, product=self.product, quantity=3, reserved_quantity=4)
        inactive_user = get_user_model().objects.create_user(
            username="integrity-inactive",
            email="inactive@example.com",
            password="pass1234",  # pragma: allowlist secret
            is_active=False,
        )
        ShipmentTrackingAccessGrant.objects.create(
            user=inactive_user,
            role=ShipmentTrackingAccessRole.SHIPPER,
            contact=self.shipper,
            is_active=True,
            expires_at=timezone.now() + timedelta(days=30),
        )
        document = AccountDocument.objects.create(
            association_contact=self.shipper,
            doc_type="legal_registration",
            file="account_documents/integrity.pdf",
            scan_status=DocumentScanStatus.CLEAN,
        )
        AccountDocument.objects.filter(pk=document.pk).update(scan_status="unchecked")
        inactive_synced_contact = Contact.objects.create(
            name="Inactive synced recipient",
            contact_type=ContactType.ORGANIZATION,
            is_active=False,
        )
        AssociationRecipient.objects.create(
            association_contact=self.shipper,
            synced_contact=inactive_synced_contact,
            destination=self.destination,
            name="Inactive synced recipient",
            structure_name="Inactive synced recipient",
            address_line1="1 rue Integrity",
            city="Integrity City",
            country="France",
            is_active=True,
        )
        out = StringIO()

        call_command("check_referential_integrity", "--report-only", stdout=out)

        text = out.getvalue()
        self.assertIn("shipment.invalid_status", text)
        self.assertIn("shipment.missing_destination", text)
        self.assertIn("carton.shipped_without_shipment", text)
        self.assertIn("stock.reserved_gt_on_hand", text)
        self.assertIn("order_line.reserved_gt_quantity", text)
        self.assertIn("tracking_grant.inactive_user", text)
        self.assertIn("document.invalid_scan_status", text)
        self.assertIn("association_recipient.inactive_synced_contact", text)

    def test_command_fails_by_default_when_issues_are_detected(self):
        shipment = self._create_valid_shipment()
        Shipment.objects.filter(pk=shipment.pk).update(status="unknown")

        with self.assertRaisesMessage(CommandError, "Referential integrity check failed"):
            call_command("check_referential_integrity")
