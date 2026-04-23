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
    CartonItem,
    CartonSourceKind,
    CartonStatus,
    Destination,
    DocumentScanStatus,
    Location,
    Order,
    OrderLine,
    OrderReservation,
    Product,
    ProductLot,
    Shipment,
    ShipmentStatus,
    ShipmentTrackingAccessGrant,
    ShipmentTrackingAccessRole,
    VolunteerProfile,
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

    def test_command_reports_remaining_issue_families_in_report_only_mode(self):
        inactive_shipper = Contact.objects.create(
            name="Inactive shipper",
            contact_type=ContactType.ORGANIZATION,
            is_active=False,
        )
        inactive_recipient = Contact.objects.create(
            name="Inactive recipient",
            contact_type=ContactType.ORGANIZATION,
            is_active=False,
        )
        inactive_correspondent = Contact.objects.create(
            name="Inactive correspondent",
            contact_type=ContactType.PERSON,
            is_active=False,
        )
        Shipment.objects.create(
            status=ShipmentStatus.PACKED,
            shipper_name=inactive_shipper.name,
            shipper_contact_ref=inactive_shipper,
            recipient_name=inactive_recipient.name,
            recipient_contact_ref=inactive_recipient,
            correspondent_name=inactive_correspondent.name,
            correspondent_contact_ref=inactive_correspondent,
            destination=self.destination,
            destination_address="1 rue Integrity",
            destination_country="France",
            created_by=self.user,
        )
        invalid_carton = Carton.objects.create(code="CART-INVALID")
        Carton.objects.filter(pk=invalid_carton.pk).update(status="invalid")
        Carton.objects.create(
            code="CART-SHIPPER-RECEIVED",
            source_kind=CartonSourceKind.SHIPPER_RECEIVED,
        )
        lot = ProductLot.objects.create(
            product=self.product,
            location=self.location,
            quantity_on_hand=1,
            quantity_reserved=0,
        )
        CartonItem.objects.create(carton=invalid_carton, product_lot=lot, quantity=0)
        ProductLot.objects.filter(pk=lot.pk).update(
            status="invalid",
            quantity_on_hand=-1,
            quantity_reserved=-2,
        )
        over_reserved_lot = ProductLot.objects.create(
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
        prepared_line = OrderLine.objects.create(order=order, product=self.product, quantity=3)
        OrderLine.objects.filter(pk=prepared_line.pk).update(prepared_quantity=4)
        reservation_line = OrderLine.objects.create(
            order=order,
            product=Product.objects.create(name="Integrity Product 2"),
            quantity=2,
        )
        OrderReservation.objects.create(
            order_line=reservation_line,
            product_lot=over_reserved_lot,
            quantity=3,
        )
        active_user = get_user_model().objects.create_user(
            username="tracking-inactive-contact-user",
            email="tracking-inactive-contact@example.com",
            password="pass1234",  # pragma: allowlist secret
        )
        ShipmentTrackingAccessGrant.objects.create(
            user=active_user,
            role=ShipmentTrackingAccessRole.SHIPPER,
            contact=inactive_shipper,
            is_active=True,
            expires_at=timezone.now() + timedelta(days=30),
        )
        inactive_volunteer_user = get_user_model().objects.create_user(
            username="inactive-volunteer",
            email="inactive-volunteer@example.com",
            password="pass1234",  # pragma: allowlist secret
        )
        inactive_volunteer = VolunteerProfile.objects.create(
            user=inactive_volunteer_user,
            is_active=False,
        )
        ShipmentTrackingAccessGrant.objects.create(
            user=inactive_volunteer_user,
            role=ShipmentTrackingAccessRole.VOLUNTEER,
            volunteer_profile=inactive_volunteer,
            is_active=True,
            expires_at=timezone.now() + timedelta(days=30),
        )
        ShipmentTrackingAccessGrant.objects.create(
            user=get_user_model().objects.create_user(
                username="expired-active-grant",
                email="expired-active-grant@example.com",
                password="pass1234",  # pragma: allowlist secret
            ),
            role=ShipmentTrackingAccessRole.RECIPIENT,
            contact=self.recipient,
            is_active=True,
            expires_at=timezone.now() - timedelta(minutes=1),
        )
        AssociationRecipient.objects.create(
            association_contact=self.shipper,
            synced_contact=self.correspondent,
            destination=self.destination,
            name="Person synced recipient",
            structure_name="Person synced recipient",
            address_line1="1 rue Integrity",
            city="Integrity City",
            country="France",
            is_active=True,
        )
        out = StringIO()

        call_command("check_referential_integrity", "--report-only", stdout=out)

        text = out.getvalue()
        self.assertIn("shipment.inactive_shipper_contact", text)
        self.assertIn("shipment.inactive_recipient_contact", text)
        self.assertIn("shipment.inactive_correspondent_contact", text)
        self.assertIn("carton.invalid_status", text)
        self.assertIn("carton.shipper_received_without_receipt", text)
        self.assertIn("carton_item.non_positive_quantity", text)
        self.assertIn("stock.invalid_lot_status", text)
        self.assertIn("stock.negative_on_hand", text)
        self.assertIn("stock.negative_reserved", text)
        self.assertIn("stock.reserved_gt_on_hand", text)
        self.assertIn("order_line.prepared_gt_quantity", text)
        self.assertIn("order_line.reservation_total_gt_quantity", text)
        self.assertIn("tracking_grant.inactive_contact", text)
        self.assertIn("tracking_grant.inactive_volunteer", text)
        self.assertIn("tracking_grant.expired_active_grant", text)
        self.assertIn("association_recipient.synced_contact_not_organization", text)

    def test_command_fails_by_default_when_issues_are_detected(self):
        shipment = self._create_valid_shipment()
        Shipment.objects.filter(pk=shipment.pk).update(status="unknown")

        with self.assertRaisesMessage(CommandError, "Referential integrity check failed"):
            call_command("check_referential_integrity")

    def test_command_rejects_negative_max_details(self):
        with self.assertRaisesMessage(CommandError, "--max-details doit etre >= 0"):
            call_command("check_referential_integrity", "--max-details=-1")

    def test_command_reports_additional_issue_count_when_details_are_limited(self):
        first = self._create_valid_shipment()
        second = self._create_valid_shipment()
        Shipment.objects.filter(pk__in=[first.pk, second.pk]).update(status="unknown")
        out = StringIO()

        call_command(
            "check_referential_integrity",
            "--report-only",
            "--max-details=1",
            stdout=out,
        )

        self.assertIn("1 additional issue(s)", out.getvalue())
