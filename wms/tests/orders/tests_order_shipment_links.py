from django.contrib.auth import get_user_model
from django.test import TestCase

from contacts.models import Contact, ContactType
from wms.models import (
    AssociationPickupAddress,
    Order,
    OrderDocumentType,
    OrderInboundArrivalMode,
    OrderInboundDelivery,
    OrderShipmentLink,
    Receipt,
    Shipment,
    Warehouse,
)


class OrderShipmentLinksTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="order-link-user",
            password="pass1234",  # pragma: allowlist secret
        )
        self.shipper = Contact.objects.create(
            name="Order Link Shipper",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        self.recipient = Contact.objects.create(
            name="Order Link Recipient",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        self.warehouse = Warehouse.objects.create(name="WH-LINK", code="WHL")
        self.order = Order.objects.create(
            shipper_name=self.shipper.name,
            shipper_contact=self.shipper,
            recipient_name=self.recipient.name,
            recipient_contact=self.recipient,
            destination_address="1 Rue Test",
            destination_city="Paris",
            destination_country="France",
            created_by=self.user,
        )

    def test_order_can_link_many_shipments(self):
        shipment_a = Shipment.objects.create(
            shipper_name=self.shipper.name,
            shipper_contact_ref=self.shipper,
            recipient_name=self.recipient.name,
            recipient_contact_ref=self.recipient,
        )
        shipment_b = Shipment.objects.create(
            shipper_name=self.shipper.name,
            shipper_contact_ref=self.shipper,
            recipient_name=self.recipient.name,
            recipient_contact_ref=self.recipient,
        )

        OrderShipmentLink.objects.create(
            order=self.order, shipment=shipment_a, created_by=self.user
        )
        OrderShipmentLink.objects.create(
            order=self.order, shipment=shipment_b, created_by=self.user
        )

        self.assertEqual(self.order.shipment_links.count(), 2)

    def test_order_can_store_inbound_delivery_with_receipt(self):
        receipt = Receipt.objects.create(
            warehouse=self.warehouse,
            source_contact=self.shipper,
        )

        inbound_delivery = OrderInboundDelivery.objects.create(
            order=self.order,
            arrival_mode=OrderInboundArrivalMode.DROPOFF_WAREHOUSE,
            declared_carton_count=4,
            declared_out_of_format_count=1,
            receipt=receipt,
        )

        self.assertEqual(inbound_delivery.receipt_id, receipt.id)
        self.assertEqual(inbound_delivery.order_id, self.order.id)

    def test_association_pickup_address_belongs_to_shipper_contact(self):
        pickup_address = AssociationPickupAddress.objects.create(
            association_contact=self.shipper,
            label="Depot principal",
            pickup_contact_name="Alice",
            pickup_contact_phone="0102030405",
            pickup_address_line1="12 Rue Logistique",
            pickup_postal_code="75010",
            pickup_city="Paris",
            pickup_country="France",
            pickup_opening_slot_1_start="09:00",
            pickup_opening_slot_1_end="12:00",
            pickup_has_no_access_constraints=True,
            tail_lift_required=True,
            pallet_truck_required=True,
        )

        self.assertEqual(pickup_address.association_contact_id, self.shipper.id)

    def test_order_document_type_exposes_packing_list_choices(self):
        doc_types = {value for value, _label in OrderDocumentType.choices}
        self.assertIn(OrderDocumentType.PACKING_LIST_GLOBAL, doc_types)
        self.assertIn(OrderDocumentType.PACKING_LIST_BY_CARTON, doc_types)

    def test_shipper_contact_can_be_humanitarian_attestation_exempt(self):
        self.shipper.is_humanitarian_attestation_exempt = True
        self.shipper.save(update_fields=["is_humanitarian_attestation_exempt"])

        self.shipper.refresh_from_db()

        self.assertTrue(self.shipper.is_humanitarian_attestation_exempt)
