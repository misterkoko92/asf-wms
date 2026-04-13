from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from wms.models import (
    AssociationPickupAddress,
    DocumentScanStatus,
    Order,
    OrderDocumentType,
    OrderInboundArrivalMode,
    OrderReviewStatus,
    ShipmentRecipientOrganization,
    ShipmentValidationStatus,
)
from wms.portal_recipient_sync import sync_association_recipient_to_contact
from wms.tests.views.tests_views_portal import PortalBaseTestCase


class PortalOrderInboundFlowTests(PortalBaseTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.user = cls._create_portal_user("portal-inbound-user", "portal-inbound@example.com")
        cls.profile = cls._create_profile(cls.user, with_address=True)
        cls.delivery_recipient = cls._create_delivery_recipient(cls.profile)
        sync_association_recipient_to_contact(cls.delivery_recipient)
        shipment_recipient = ShipmentRecipientOrganization.objects.get(
            organization=cls.delivery_recipient.synced_contact,
            destination=cls.delivery_recipient.destination,
        )
        shipment_recipient.validation_status = ShipmentValidationStatus.VALIDATED
        shipment_recipient.save(update_fields=["validation_status"])

    def setUp(self):
        self.client.force_login(self.user)
        self.order_create_url = reverse("portal:portal_order_create")

    def _base_payload(self):
        return {
            "destination_id": str(self.delivery_recipient.destination_id),
            "recipient_id": str(self.delivery_recipient.id),
            "notes": "Flux inbound expéditeur",
            "has_shipper_inbound": "1",
            "declared_carton_count": "4",
            "declared_out_of_format_count": "1",
        }

    def test_portal_order_create_supports_shipper_inbound_dropoff_without_documents(self):
        payload = self._base_payload()
        payload["arrival_mode"] = OrderInboundArrivalMode.DROPOFF_WAREHOUSE

        with mock.patch("wms.views_portal_orders.send_portal_order_notifications"):
            response = self.client.post(self.order_create_url, payload)

        self.assertEqual(response.status_code, 302)
        order = Order.objects.filter(association_contact=self.profile.contact).latest("id")
        self.assertEqual(
            order.inbound_delivery.arrival_mode, OrderInboundArrivalMode.DROPOFF_WAREHOUSE
        )
        self.assertEqual(order.inbound_delivery.declared_carton_count, 4)
        self.assertEqual(order.inbound_delivery.declared_out_of_format_count, 1)

    def test_portal_order_create_requires_pickup_phone(self):
        payload = self._base_payload()
        payload.update(
            {
                "arrival_mode": OrderInboundArrivalMode.PICKUP_REQUESTED,
                "pickup_contact_name": "Alice",
                "pickup_contact_phone": "",
                "pickup_contact_phone_2": "",
                "pickup_address_line1": "12 Rue Logistique",
                "pickup_postal_code": "75010",
                "pickup_city": "Paris",
                "pickup_country": "France",
                "pickup_available_from_date": "2026-04-20",
                "pickup_opening_slot_1_start": "09:00",
                "pickup_opening_slot_1_end": "12:00",
                "pickup_has_no_access_constraints": "1",
                "tail_lift_required": "1",
                "pallet_truck_required": "1",
                "pickup_information_confirmed": "1",
            }
        )

        response = self.client.post(self.order_create_url, payload)

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response, "Au moins un numéro de téléphone est requis pour l&#x27;enlèvement."
        )
        self.assertFalse(Order.objects.filter(association_contact=self.profile.contact).exists())

    def test_portal_order_create_accepts_pickup_without_desired_pickup_date(self):
        payload = self._base_payload()
        payload.update(
            {
                "arrival_mode": OrderInboundArrivalMode.PICKUP_REQUESTED,
                "pickup_contact_name": "Alice",
                "pickup_contact_phone": "0102030405",
                "pickup_address_line1": "12 Rue Logistique",
                "pickup_postal_code": "75010",
                "pickup_city": "Paris",
                "pickup_country": "France",
                "pickup_available_from_date": "2026-04-20",
                "pickup_opening_slot_1_start": "09:00",
                "pickup_opening_slot_1_end": "12:00",
                "pickup_has_no_access_constraints": "1",
                "tail_lift_required": "1",
                "pallet_truck_required": "1",
                "pickup_information_confirmed": "1",
            }
        )

        with mock.patch("wms.views_portal_orders.send_portal_order_notifications"):
            response = self.client.post(self.order_create_url, payload)

        self.assertEqual(response.status_code, 302)
        order = Order.objects.filter(association_contact=self.profile.contact).latest("id")
        self.assertEqual(
            order.inbound_delivery.arrival_mode, OrderInboundArrivalMode.PICKUP_REQUESTED
        )
        self.assertIsNone(order.inbound_delivery.pickup_requested_for_date)

    def test_portal_order_detail_allows_upload_before_approval(self):
        order = Order.objects.create(
            association_contact=self.profile.contact,
            shipper_name=self.profile.contact.name,
            shipper_contact=self.profile.contact,
            recipient_name=self.delivery_recipient.name,
            destination_address="1 Rue Test",
            destination_city=self.delivery_recipient.destination.city,
            destination_country=self.delivery_recipient.destination.country,
            review_status=OrderReviewStatus.PENDING,
        )

        response = self.client.post(
            reverse("portal:portal_order_detail", kwargs={"order_id": order.id}),
            {
                "action": "upload_docs",
                "doc_file_invoice": SimpleUploadedFile("invoice.pdf", b"%PDF-1.4 invoice"),
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(order.documents.count(), 1)
        document = order.documents.get()
        self.assertEqual(document.doc_type, OrderDocumentType.INVOICE)
        self.assertEqual(document.scan_status, DocumentScanStatus.PENDING)

    def test_portal_order_create_saves_pickup_address_when_requested(self):
        payload = self._base_payload()
        payload.update(
            {
                "arrival_mode": OrderInboundArrivalMode.PICKUP_REQUESTED,
                "save_pickup_address": "1",
                "pickup_company_name": "Logistique ASF",
                "pickup_contact_name": "Alice",
                "pickup_contact_phone": "0102030405",
                "pickup_address_line1": "12 Rue Logistique",
                "pickup_postal_code": "75010",
                "pickup_city": "Paris",
                "pickup_country": "France",
                "pickup_available_from_date": "2026-04-20",
                "pickup_opening_slot_1_start": "09:00",
                "pickup_opening_slot_1_end": "12:00",
                "pickup_has_no_access_constraints": "1",
                "tail_lift_required": "1",
                "pallet_truck_required": "1",
                "pickup_information_confirmed": "1",
            }
        )

        with mock.patch("wms.views_portal_orders.send_portal_order_notifications"):
            response = self.client.post(self.order_create_url, payload)

        self.assertEqual(response.status_code, 302)
        order = Order.objects.filter(association_contact=self.profile.contact).latest("id")
        self.assertIsNotNone(order.inbound_delivery.pickup_address_book_entry_id)
        address_entry = order.inbound_delivery.pickup_address_book_entry
        self.assertEqual(address_entry.association_contact_id, self.profile.contact_id)
        self.assertEqual(address_entry.pickup_address_line1, "12 Rue Logistique")
        self.assertEqual(address_entry.times_used, 1)

    def test_portal_order_create_can_reuse_saved_pickup_address(self):
        address_entry = AssociationPickupAddress.objects.create(
            association_contact=self.profile.contact,
            label="Entrepôt Paris",
            pickup_company_name="Logistique ASF",
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
            pickup_information_confirmed=True,
        )
        payload = self._base_payload()
        payload.update(
            {
                "arrival_mode": OrderInboundArrivalMode.PICKUP_REQUESTED,
                "pickup_address_book_entry_id": str(address_entry.id),
                "pickup_available_from_date": "2026-04-20",
                "pickup_information_confirmed": "1",
            }
        )

        with mock.patch("wms.views_portal_orders.send_portal_order_notifications"):
            response = self.client.post(self.order_create_url, payload)

        self.assertEqual(response.status_code, 302)
        order = Order.objects.filter(association_contact=self.profile.contact).latest("id")
        self.assertEqual(order.inbound_delivery.pickup_address_book_entry_id, address_entry.id)
        self.assertEqual(order.inbound_delivery.pickup_contact_name, "Alice")
        self.assertEqual(order.inbound_delivery.pickup_address_line1, "12 Rue Logistique")
