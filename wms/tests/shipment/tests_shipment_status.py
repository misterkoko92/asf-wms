import tempfile
from datetime import timedelta
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.test.utils import override_settings
from django.utils import timezone

from contacts.models import Contact, ContactType
from wms.document_scan import DocumentScanStatus
from wms.domain.stock import StockError
from wms.models import (
    Carton,
    CartonSourceKind,
    CartonStatus,
    Order,
    OrderDocument,
    OrderDocumentType,
    OrderInboundArrivalMode,
    OrderInboundDelivery,
    OrderShipmentLink,
    Receipt,
    ReceiptConformityStatus,
    ReceiptType,
    Shipment,
    ShipmentStatus,
    Warehouse,
)
from wms.shipment_status import (
    compute_shipment_progress,
    confirm_shipment_ready,
    shipment_can_be_confirmed_ready,
    sync_shipment_ready_state,
)


@override_settings(MEDIA_ROOT=tempfile.gettempdir())
class ShipmentStatusTests(TestCase):
    def _create_shipment(self, *, status=ShipmentStatus.DRAFT):
        return Shipment.objects.create(
            status=status,
            shipper_name="Sender",
            recipient_name="Recipient",
            destination_address="1 Rue Test",
            destination_country="France",
        )

    def _create_contact(self, name, *, exempt=False):
        return Contact.objects.create(
            name=name,
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
            is_humanitarian_attestation_exempt=exempt,
        )

    def _create_linked_order_and_second_shipment(self, *, exempt=False):
        shipper = self._create_contact("Sender Org", exempt=exempt)
        recipient = self._create_contact("Recipient Org")
        order = Order.objects.create(
            association_contact=shipper,
            shipper_name=shipper.name,
            shipper_contact=shipper,
            recipient_name=recipient.name,
            recipient_contact=recipient,
            destination_address="1 Rue Test",
            destination_country="France",
        )
        first_shipment = self._create_shipment(status=ShipmentStatus.DRAFT)
        second_shipment = self._create_shipment(status=ShipmentStatus.PICKING)
        order.shipment = first_shipment
        order.save(update_fields=["shipment"])
        OrderShipmentLink.objects.create(order=order, shipment=first_shipment)
        OrderShipmentLink.objects.create(order=order, shipment=second_shipment)
        return order, second_shipment

    def _create_clean_order_document(self, *, order, doc_type, filename):
        return OrderDocument.objects.create(
            order=order,
            doc_type=doc_type,
            file=SimpleUploadedFile(filename, b"%PDF-1.4"),
            scan_status=DocumentScanStatus.CLEAN,
        )

    def test_compute_shipment_progress_returns_partial_when_not_all_cartons_ready(self):
        shipment = self._create_shipment(status=ShipmentStatus.DRAFT)
        Carton.objects.create(code="CT-SS-1", shipment=shipment, status=CartonStatus.LABELED)
        Carton.objects.create(code="CT-SS-2", shipment=shipment, status=CartonStatus.ASSIGNED)

        total, ready, status, label = compute_shipment_progress(shipment)

        self.assertEqual((total, ready), (2, 1))
        self.assertEqual(status, ShipmentStatus.PICKING)
        self.assertEqual(label, "EN COURS (1/2)")

    def test_sync_shipment_ready_state_short_circuits_for_shipped(self):
        shipment = self._create_shipment(status=ShipmentStatus.SHIPPED)

        with mock.patch.object(shipment, "save") as save_mock:
            sync_shipment_ready_state(shipment)

        save_mock.assert_not_called()

    def test_sync_shipment_ready_state_clears_ready_at_when_no_longer_packed(self):
        shipment = self._create_shipment(status=ShipmentStatus.PACKED)
        shipment.ready_at = timezone.now() - timedelta(hours=1)
        shipment.save(update_fields=["ready_at"])
        Carton.objects.create(code="CT-SS-3", shipment=shipment, status=CartonStatus.DRAFT)

        sync_shipment_ready_state(shipment)
        shipment.refresh_from_db()

        self.assertEqual(shipment.status, ShipmentStatus.PICKING)
        self.assertIsNone(shipment.ready_at)

    def test_planned_carton_count_defaults_to_zero_and_does_not_create_cartons(self):
        shipment = self._create_shipment(status=ShipmentStatus.DRAFT)

        self.assertEqual(shipment.planned_carton_count, 0)
        self.assertEqual(shipment.carton_set.count(), 0)

    def test_planned_carton_count_does_not_make_shipment_ready_without_real_cartons(self):
        shipment = self._create_shipment(status=ShipmentStatus.PICKING)
        shipment.planned_carton_count = 10
        shipment.save(update_fields=["planned_carton_count"])

        self.assertFalse(shipment_can_be_confirmed_ready(shipment))

    def test_confirm_shipment_ready_marks_assigned_cartons_labeled_and_sets_shipment_packed(self):
        shipment = self._create_shipment(status=ShipmentStatus.PICKING)
        carton = Carton.objects.create(
            code="CT-SS-4", shipment=shipment, status=CartonStatus.ASSIGNED
        )

        self.assertTrue(shipment_can_be_confirmed_ready(shipment))

        confirm_shipment_ready(shipment=shipment, user=None)
        shipment.refresh_from_db()
        carton.refresh_from_db()

        self.assertEqual(carton.status, CartonStatus.LABELED)
        self.assertEqual(shipment.status, ShipmentStatus.PACKED)
        self.assertIsNotNone(shipment.ready_at)

    def test_confirm_shipment_ready_rejects_when_any_carton_is_not_ready(self):
        shipment = self._create_shipment(status=ShipmentStatus.PICKING)
        Carton.objects.create(code="CT-SS-5", shipment=shipment, status=CartonStatus.PICKING)

        self.assertFalse(shipment_can_be_confirmed_ready(shipment))

        with self.assertRaises(StockError):
            confirm_shipment_ready(shipment=shipment, user=None)

    def test_confirm_shipment_ready_uses_order_links_for_additional_shipments(self):
        order, shipment = self._create_linked_order_and_second_shipment(exempt=True)
        carton = Carton.objects.create(
            code="CT-SS-LINK-1",
            shipment=shipment,
            status=CartonStatus.ASSIGNED,
        )

        self.assertFalse(shipment_can_be_confirmed_ready(shipment))

        self._create_clean_order_document(
            order=order,
            doc_type=OrderDocumentType.DONATION_ATTESTATION,
            filename="donation.pdf",
        )

        self.assertTrue(shipment_can_be_confirmed_ready(shipment))
        confirm_shipment_ready(shipment=shipment, user=None)
        shipment.refresh_from_db()
        carton.refresh_from_db()
        self.assertEqual(shipment.status, ShipmentStatus.PACKED)
        self.assertEqual(carton.status, CartonStatus.LABELED)

    def test_confirm_shipment_ready_requires_receipt_and_packing_lists_for_shipper_cartons(self):
        order, shipment = self._create_linked_order_and_second_shipment(exempt=True)
        OrderInboundDelivery.objects.create(
            order=order,
            arrival_mode=OrderInboundArrivalMode.DROPOFF_WAREHOUSE,
            declared_carton_count=1,
            declared_out_of_format_count=0,
        )
        Carton.objects.create(
            code="CT-SS-SHIPPER-1",
            shipment=shipment,
            status=CartonStatus.ASSIGNED,
            source_kind=CartonSourceKind.SHIPPER_RECEIVED,
        )
        self._create_clean_order_document(
            order=order,
            doc_type=OrderDocumentType.DONATION_ATTESTATION,
            filename="donation-shipper.pdf",
        )

        self.assertFalse(shipment_can_be_confirmed_ready(shipment))

        receipt = Receipt.objects.create(
            receipt_type=ReceiptType.ASSOCIATION,
            conformity_status=ReceiptConformityStatus.CONFORM,
            warehouse=Warehouse.objects.create(name="WH-SS", code="WHSS"),
            source_contact=order.shipper_contact,
        )
        inbound_delivery = order.inbound_delivery
        inbound_delivery.receipt = receipt
        inbound_delivery.save(update_fields=["receipt"])
        self._create_clean_order_document(
            order=order,
            doc_type=OrderDocumentType.PACKING_LIST_GLOBAL,
            filename="packing-global.pdf",
        )
        self._create_clean_order_document(
            order=order,
            doc_type=OrderDocumentType.PACKING_LIST_BY_CARTON,
            filename="packing-carton.pdf",
        )

        self.assertTrue(shipment_can_be_confirmed_ready(shipment))

    def test_confirm_shipment_ready_blocks_non_conform_shipper_receipt(self):
        order, shipment = self._create_linked_order_and_second_shipment(exempt=True)
        receipt = Receipt.objects.create(
            receipt_type=ReceiptType.ASSOCIATION,
            conformity_status=ReceiptConformityStatus.NON_CONFORM,
            warehouse=Warehouse.objects.create(name="WH-SS-NC", code="WHNC"),
            source_contact=order.shipper_contact,
        )
        OrderInboundDelivery.objects.create(
            order=order,
            arrival_mode=OrderInboundArrivalMode.DROPOFF_WAREHOUSE,
            declared_carton_count=1,
            declared_out_of_format_count=0,
            receipt=receipt,
        )
        Carton.objects.create(
            code="CT-SS-SHIPPER-2",
            shipment=shipment,
            status=CartonStatus.ASSIGNED,
            source_kind=CartonSourceKind.SHIPPER_RECEIVED,
        )
        self._create_clean_order_document(
            order=order,
            doc_type=OrderDocumentType.DONATION_ATTESTATION,
            filename="donation-non-conform.pdf",
        )
        self._create_clean_order_document(
            order=order,
            doc_type=OrderDocumentType.PACKING_LIST_GLOBAL,
            filename="packing-global-nc.pdf",
        )
        self._create_clean_order_document(
            order=order,
            doc_type=OrderDocumentType.PACKING_LIST_BY_CARTON,
            filename="packing-carton-nc.pdf",
        )

        self.assertFalse(shipment_can_be_confirmed_ready(shipment))

        with self.assertRaises(StockError):
            confirm_shipment_ready(shipment=shipment, user=None)
