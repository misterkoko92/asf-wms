from django.contrib.auth import get_user_model
from django.db.models import Sum
from django.test import TestCase
from rest_framework.test import APIClient

from contacts.models import Contact, ContactTag, ContactType
from wms.models import (
    AssociationProfile,
    Carton,
    CartonStatus,
    Destination,
    Location,
    Order,
    OrderReviewStatus,
    Product,
    ProductLot,
    ProductLotStatus,
    Shipment,
    ShipmentStatus,
    ShipmentTrackingEvent,
    ShipmentTrackingStatus,
    Warehouse,
)


class UiApiEndpointsTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.staff_user = user_model.objects.create_user(
            username="ui-api-staff",
            password="pass1234",
            is_staff=True,
        )
        self.basic_user = user_model.objects.create_user(
            username="ui-api-basic",
            password="pass1234",
        )
        self.portal_user = user_model.objects.create_user(
            username="ui-api-portal",
            password="pass1234",
        )

        association_contact = Contact.objects.create(
            name="Association UI API",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        AssociationProfile.objects.create(
            user=self.portal_user,
            contact=association_contact,
        )

        self.staff_client = APIClient()
        self.staff_client.force_authenticate(self.staff_user)
        self.basic_client = APIClient()
        self.basic_client.force_authenticate(self.basic_user)
        self.portal_client = APIClient()
        self.portal_client.force_authenticate(self.portal_user)

        warehouse = Warehouse.objects.create(name="UI API WH", code="UIA")
        location = Location.objects.create(
            warehouse=warehouse,
            zone="A",
            aisle="01",
            shelf="001",
        )
        self.product = Product.objects.create(
            sku="UI-API-001",
            name="UI API Product",
            brand="Medi",
            default_location=location,
            is_active=True,
            qr_code_image="qr_codes/test.png",
        )
        ProductLot.objects.create(
            product=self.product,
            lot_code="LOT-LOW",
            status=ProductLotStatus.AVAILABLE,
            quantity_on_hand=15,
            quantity_reserved=0,
            location=location,
        )

        self.correspondent_contact = self._create_contact(
            "UI Correspondent",
            tags=["correspondant"],
            contact_type=ContactType.PERSON,
        )
        self.destination = Destination.objects.create(
            city="RUN",
            iata_code="RUN",
            country="France",
            correspondent_contact=self.correspondent_contact,
            is_active=True,
        )
        self.correspondent_contact.destinations.add(self.destination)

        self.shipper_contact = self._create_contact(
            "UI Shipper",
            tags=["expediteur"],
        )
        self.shipper_contact.destinations.add(self.destination)

        self.recipient_contact = self._create_contact(
            "UI Recipient",
            tags=["destinataire"],
        )
        self.recipient_contact.destinations.add(self.destination)

        self.donor_contact = self._create_contact(
            "UI Donor",
            tags=["donateur"],
        )

        self.available_carton = Carton.objects.create(
            code="UI-CARTON-AVAILABLE",
            status=CartonStatus.PACKED,
        )

        self.shipment = Shipment.objects.create(
            status=ShipmentStatus.PLANNED,
            shipper_name="ASF Hub",
            shipper_contact_ref=self.shipper_contact,
            recipient_name="CHU Nord",
            recipient_contact_ref=self.recipient_contact,
            correspondent_name="M. Dupont",
            correspondent_contact_ref=self.correspondent_contact,
            destination=self.destination,
            destination_address="1 Rue Test",
            destination_country="France",
            created_by=self.staff_user,
        )
        ShipmentTrackingEvent.objects.create(
            shipment=self.shipment,
            status=ShipmentTrackingStatus.PLANNED,
            comments="Planned",
            created_by=self.staff_user,
            actor_name="Ops",
            actor_structure="ASF",
        )

        Order.objects.create(
            review_status=OrderReviewStatus.PENDING,
            shipper_name="Sender",
            recipient_name="Recipient",
            correspondent_name="Correspondent",
            destination_address="10 Rue Test",
            destination_country="France",
            created_by=self.staff_user,
        )
        self.portal_order = Order.objects.create(
            association_contact=association_contact,
            review_status=OrderReviewStatus.PENDING,
            shipper_name="Sender",
            recipient_name="Recipient",
            correspondent_name="Correspondent",
            destination_address="20 Rue Test",
            destination_country="France",
            created_by=self.staff_user,
        )

    def _create_contact(self, name, *, tags, contact_type=ContactType.ORGANIZATION):
        contact = Contact.objects.create(
            name=name,
            contact_type=contact_type,
            is_active=True,
        )
        for tag_name in tags:
            tag, _ = ContactTag.objects.get_or_create(name=tag_name)
            contact.tags.add(tag)
        return contact

    def _shipment_mutation_payload(self, *, lines):
        return {
            "destination": self.destination.id,
            "shipper_contact": self.shipper_contact.id,
            "recipient_contact": self.recipient_contact.id,
            "correspondent_contact": self.correspondent_contact.id,
            "lines": lines,
        }

    def test_ui_dashboard_requires_staff(self):
        anonymous = APIClient()
        response = anonymous.get("/api/v1/ui/dashboard/")
        self.assertEqual(response.status_code, 403)

        response = self.basic_client.get("/api/v1/ui/dashboard/")
        self.assertEqual(response.status_code, 403)

        response = self.staff_client.get("/api/v1/ui/dashboard/")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("kpis", payload)
        self.assertIn("timeline", payload)
        self.assertIn("pending_actions", payload)

    def test_ui_stock_returns_products_and_filters(self):
        response = self.staff_client.get("/api/v1/ui/stock/?q=UI%20API")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["filters"]["q"], "UI API")
        self.assertEqual(payload["meta"]["total_products"], 1)
        self.assertEqual(payload["products"][0]["sku"], self.product.sku)

    def test_ui_shipment_form_options_returns_collections(self):
        response = self.staff_client.get("/api/v1/ui/shipments/form-options/")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("products", payload)
        self.assertIn("available_cartons", payload)
        self.assertIn("destinations", payload)
        self.assertIn("shipper_contacts", payload)
        self.assertIn("recipient_contacts", payload)
        self.assertIn("correspondent_contacts", payload)

    def test_ui_portal_dashboard_requires_association_profile(self):
        response = self.basic_client.get("/api/v1/ui/portal/dashboard/")
        self.assertEqual(response.status_code, 403)

        response = self.portal_client.get("/api/v1/ui/portal/dashboard/")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("kpis", payload)
        self.assertIn("orders", payload)
        self.assertEqual(payload["orders"][0]["id"], self.portal_order.id)

    def test_ui_stock_update_post_creates_new_lot(self):
        previous_lot_count = ProductLot.objects.count()
        response = self.staff_client.post(
            "/api/v1/ui/stock/update/",
            {
                "product_code": self.product.sku,
                "quantity": 4,
                "expires_on": "2026-12-31",
                "lot_code": "LOT-NEW",
                "donor_contact_id": self.donor_contact.id,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(ProductLot.objects.count(), previous_lot_count + 1)

    def test_ui_stock_update_invalid_payload_uses_uniform_error_shape(self):
        response = self.staff_client.post(
            "/api/v1/ui/stock/update/",
            {
                "product_code": self.product.sku,
                "quantity": 0,
                "expires_on": "2026-12-31",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["code"], "validation_error")
        self.assertIn("quantity", payload["field_errors"])
        self.assertIn("message", payload)
        self.assertIn("non_field_errors", payload)

    def test_ui_stock_out_post_consumes_available_quantity(self):
        before_total = ProductLot.objects.filter(product=self.product).aggregate(
            total=Sum("quantity_on_hand")
        )["total"]
        response = self.staff_client.post(
            "/api/v1/ui/stock/out/",
            {
                "product_code": self.product.sku,
                "quantity": 3,
                "reason_code": "test_out",
                "reason_notes": "UI API out",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        after_total = ProductLot.objects.filter(product=self.product).aggregate(
            total=Sum("quantity_on_hand")
        )["total"]
        self.assertEqual(after_total, before_total - 3)

    def test_ui_shipment_create_assigns_and_packs_lines(self):
        response = self.staff_client.post(
            "/api/v1/ui/shipments/",
            self._shipment_mutation_payload(
                lines=[
                    {"carton_id": self.available_carton.id},
                    {"product_code": self.product.sku, "quantity": 1},
                ]
            ),
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        payload = response.json()
        shipment_id = payload["shipment"]["id"]
        self.available_carton.refresh_from_db()
        self.assertEqual(self.available_carton.shipment_id, shipment_id)
        self.assertEqual(self.available_carton.status, CartonStatus.ASSIGNED)
        self.assertGreaterEqual(Carton.objects.filter(shipment_id=shipment_id).count(), 2)

    def test_ui_shipment_create_rejects_invalid_lines_with_uniform_errors(self):
        response = self.staff_client.post(
            "/api/v1/ui/shipments/",
            self._shipment_mutation_payload(lines=[{"product_code": self.product.sku}]),
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertEqual(payload["code"], "validation_error")
        self.assertIn("lines", payload["field_errors"])

    def test_ui_shipment_update_blocks_locked_shipment(self):
        locked_shipment = Shipment.objects.create(
            status=ShipmentStatus.SHIPPED,
            shipper_name=self.shipper_contact.name,
            shipper_contact_ref=self.shipper_contact,
            recipient_name=self.recipient_contact.name,
            recipient_contact_ref=self.recipient_contact,
            correspondent_name=self.correspondent_contact.name,
            correspondent_contact_ref=self.correspondent_contact,
            destination=self.destination,
            destination_address=str(self.destination),
            destination_country=self.destination.country,
            created_by=self.staff_user,
        )
        response = self.staff_client.patch(
            f"/api/v1/ui/shipments/{locked_shipment.id}/",
            self._shipment_mutation_payload(lines=[{"carton_id": self.available_carton.id}]),
            format="json",
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["code"], "shipment_locked")

    def test_ui_shipment_update_reassigns_cartons(self):
        editable_shipment = Shipment.objects.create(
            status=ShipmentStatus.DRAFT,
            shipper_name=self.shipper_contact.name,
            shipper_contact_ref=self.shipper_contact,
            recipient_name=self.recipient_contact.name,
            recipient_contact_ref=self.recipient_contact,
            correspondent_name=self.correspondent_contact.name,
            correspondent_contact_ref=self.correspondent_contact,
            destination=self.destination,
            destination_address=str(self.destination),
            destination_country=self.destination.country,
            created_by=self.staff_user,
        )
        already_assigned = Carton.objects.create(
            code="UI-CARTON-ASSIGNED",
            status=CartonStatus.ASSIGNED,
            shipment=editable_shipment,
        )
        replacement = Carton.objects.create(
            code="UI-CARTON-REPLACEMENT",
            status=CartonStatus.PACKED,
        )

        response = self.staff_client.patch(
            f"/api/v1/ui/shipments/{editable_shipment.id}/",
            self._shipment_mutation_payload(lines=[{"carton_id": replacement.id}]),
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        already_assigned.refresh_from_db()
        replacement.refresh_from_db()
        self.assertIsNone(already_assigned.shipment_id)
        self.assertEqual(already_assigned.status, CartonStatus.PACKED)
        self.assertEqual(replacement.shipment_id, editable_shipment.id)
        self.assertEqual(replacement.status, CartonStatus.ASSIGNED)

    def test_ui_tracking_event_updates_shipment_status(self):
        track_shipment = Shipment.objects.create(
            status=ShipmentStatus.DRAFT,
            shipper_name=self.shipper_contact.name,
            shipper_contact_ref=self.shipper_contact,
            recipient_name=self.recipient_contact.name,
            recipient_contact_ref=self.recipient_contact,
            correspondent_name=self.correspondent_contact.name,
            correspondent_contact_ref=self.correspondent_contact,
            destination=self.destination,
            destination_address=str(self.destination),
            destination_country=self.destination.country,
            created_by=self.staff_user,
        )
        Carton.objects.create(
            code="UI-CARTON-LABELED",
            status=CartonStatus.LABELED,
            shipment=track_shipment,
        )

        response = self.staff_client.post(
            f"/api/v1/ui/shipments/{track_shipment.id}/tracking-events/",
            {
                "status": ShipmentTrackingStatus.PLANNING_OK,
                "actor_name": "Operateur",
                "actor_structure": "ASF",
                "comments": "Planification validee",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        track_shipment.refresh_from_db()
        self.assertEqual(track_shipment.status, ShipmentStatus.PACKED)
        self.assertEqual(
            ShipmentTrackingEvent.objects.filter(shipment=track_shipment).count(),
            1,
        )

    def test_ui_close_shipment_blocks_incomplete_case(self):
        blocked_shipment = Shipment.objects.create(
            status=ShipmentStatus.DELIVERED,
            shipper_name=self.shipper_contact.name,
            shipper_contact_ref=self.shipper_contact,
            recipient_name=self.recipient_contact.name,
            recipient_contact_ref=self.recipient_contact,
            correspondent_name=self.correspondent_contact.name,
            correspondent_contact_ref=self.correspondent_contact,
            destination=self.destination,
            destination_address=str(self.destination),
            destination_country=self.destination.country,
            created_by=self.staff_user,
        )
        response = self.staff_client.post(
            f"/api/v1/ui/shipments/{blocked_shipment.id}/close/",
            {},
            format="json",
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["code"], "shipment_close_blocked")

    def test_ui_close_shipment_succeeds_when_timeline_complete(self):
        closable = Shipment.objects.create(
            status=ShipmentStatus.DELIVERED,
            shipper_name=self.shipper_contact.name,
            shipper_contact_ref=self.shipper_contact,
            recipient_name=self.recipient_contact.name,
            recipient_contact_ref=self.recipient_contact,
            correspondent_name=self.correspondent_contact.name,
            correspondent_contact_ref=self.correspondent_contact,
            destination=self.destination,
            destination_address=str(self.destination),
            destination_country=self.destination.country,
            created_by=self.staff_user,
        )
        ShipmentTrackingEvent.objects.create(
            shipment=closable,
            status=ShipmentTrackingStatus.PLANNED,
            actor_name="Ops",
            actor_structure="ASF",
            comments="Plan",
            created_by=self.staff_user,
        )
        ShipmentTrackingEvent.objects.create(
            shipment=closable,
            status=ShipmentTrackingStatus.BOARDING_OK,
            actor_name="Ops",
            actor_structure="ASF",
            comments="Boarding",
            created_by=self.staff_user,
        )
        ShipmentTrackingEvent.objects.create(
            shipment=closable,
            status=ShipmentTrackingStatus.RECEIVED_CORRESPONDENT,
            actor_name="Ops",
            actor_structure="ASF",
            comments="Correspondent",
            created_by=self.staff_user,
        )
        ShipmentTrackingEvent.objects.create(
            shipment=closable,
            status=ShipmentTrackingStatus.RECEIVED_RECIPIENT,
            actor_name="Ops",
            actor_structure="ASF",
            comments="Delivered",
            created_by=self.staff_user,
        )
        response = self.staff_client.post(
            f"/api/v1/ui/shipments/{closable.id}/close/",
            {},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        closable.refresh_from_db()
        self.assertIsNotNone(closable.closed_at)
        self.assertEqual(closable.closed_by_id, self.staff_user.id)

    def test_ui_mutation_endpoints_require_staff(self):
        response = self.basic_client.post(
            "/api/v1/ui/stock/update/",
            {
                "product_code": self.product.sku,
                "quantity": 1,
                "expires_on": "2026-12-31",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 403)
