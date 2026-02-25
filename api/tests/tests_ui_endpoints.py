from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db.models import Sum
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from contacts.models import Contact, ContactTag, ContactType
from wms.models import (
    AssociationContactTitle,
    AssociationProfile,
    AssociationRecipient,
    Carton,
    CartonItem,
    CartonStatus,
    Document,
    DocumentType,
    Destination,
    Location,
    Order,
    OrderReviewStatus,
    PrintTemplate,
    PrintTemplateVersion,
    Product,
    ProductLot,
    ProductLotStatus,
    Shipment,
    ShipmentStatus,
    ShipmentTrackingEvent,
    ShipmentTrackingStatus,
    TEMP_SHIPMENT_REFERENCE_PREFIX,
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
        self.superuser_user = user_model.objects.create_user(
            username="ui-api-superuser",
            password="pass1234",
            is_staff=True,
            is_superuser=True,
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
        self.superuser_client = APIClient()
        self.superuser_client.force_authenticate(self.superuser_user)
        self.role_clients = {
            "staff": self.staff_client,
            "superuser": self.superuser_client,
            "basic": self.basic_client,
            "portal": self.portal_client,
        }
        for role_name in ("admin", "qualite", "magasinier", "benevole", "livreur"):
            role_user = user_model.objects.create_user(
                username=f"ui-api-{role_name}",
                password="pass1234",
                is_staff=True,
            )
            role_client = APIClient()
            role_client.force_authenticate(role_user)
            self.role_clients[role_name] = role_client
        self.staff_role_clients = {
            role_name: self.role_clients[role_name]
            for role_name in (
                "staff",
                "admin",
                "qualite",
                "magasinier",
                "benevole",
                "livreur",
                "superuser",
            )
        }

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
        self.product_lot = ProductLot.objects.create(
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
        self.ready_carton = Carton.objects.create(
            code="UI-CARTON-READY",
            status=CartonStatus.PACKED,
        )
        CartonItem.objects.create(
            carton=self.ready_carton,
            product_lot=self.product_lot,
            quantity=2,
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
        self.portal_recipient = AssociationRecipient.objects.create(
            association_contact=association_contact,
            destination=self.destination,
            name="Recipient Structure",
            structure_name="Recipient Structure",
            address_line1="1 rue recipient",
            postal_code="75001",
            city="Paris",
            country="France",
            emails="recipient@example.org",
            email="recipient@example.org",
            phones="0102030405",
            phone="0102030405",
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

    def _call_endpoint(self, client, method, path, *, payload=None, fmt="json"):
        caller = getattr(client, method.lower())
        if payload is None:
            if method.lower() in {"get", "delete"}:
                return caller(path)
            return caller(path, {}, format=fmt)
        return caller(path, payload, format=fmt)

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

    def test_ui_dashboard_destination_filter_and_options(self):
        secondary_destination = Destination.objects.create(
            city="TNR",
            iata_code="TNR-UI",
            country="Madagascar",
            correspondent_contact=self.correspondent_contact,
            is_active=True,
        )
        self.shipper_contact.destinations.add(secondary_destination)
        self.recipient_contact.destinations.add(secondary_destination)
        self.correspondent_contact.destinations.add(secondary_destination)
        Shipment.objects.create(
            status=ShipmentStatus.PLANNED,
            shipper_name=self.shipper_contact.name,
            shipper_contact_ref=self.shipper_contact,
            recipient_name=self.recipient_contact.name,
            recipient_contact_ref=self.recipient_contact,
            correspondent_name=self.correspondent_contact.name,
            correspondent_contact_ref=self.correspondent_contact,
            destination=secondary_destination,
            destination_address="9 Rue Secondary",
            destination_country="Madagascar",
            created_by=self.staff_user,
        )

        response = self.staff_client.get("/api/v1/ui/dashboard/")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("filters", payload)
        self.assertIn("destinations", payload["filters"])
        destination_ids = {
            row["id"]
            for row in payload["filters"]["destinations"]
        }
        self.assertIn(self.destination.id, destination_ids)
        self.assertIn(secondary_destination.id, destination_ids)

        filtered_response = self.staff_client.get(
            f"/api/v1/ui/dashboard/?destination={secondary_destination.id}"
        )
        self.assertEqual(filtered_response.status_code, 200)
        filtered_payload = filtered_response.json()
        self.assertEqual(
            filtered_payload["filters"]["destination"],
            str(secondary_destination.id),
        )
        self.assertEqual(filtered_payload["kpis"]["open_shipments"], 1)

    def test_ui_dashboard_period_filter_and_activity_cards(self):
        old_shipment = Shipment.objects.create(
            status=ShipmentStatus.PLANNED,
            shipper_name=self.shipper_contact.name,
            shipper_contact_ref=self.shipper_contact,
            recipient_name=self.recipient_contact.name,
            recipient_contact_ref=self.recipient_contact,
            correspondent_name=self.correspondent_contact.name,
            correspondent_contact_ref=self.correspondent_contact,
            destination=self.destination,
            destination_address="12 Rue Legacy",
            destination_country="France",
            created_by=self.staff_user,
        )
        Shipment.objects.filter(pk=old_shipment.pk).update(
            created_at=timezone.now() - timedelta(days=10)
        )

        response = self.staff_client.get("/api/v1/ui/dashboard/")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["filters"]["period"], "week")
        period_values = {
            row["value"]
            for row in payload["filters"]["period_choices"]
        }
        self.assertSetEqual(period_values, {"today", "7d", "30d", "week"})
        shipments_card = next(
            card
            for card in payload["activity_cards"]
            if card["label"] == "Expeditions creees"
        )
        self.assertEqual(shipments_card["value"], 1)

        filtered_response = self.staff_client.get("/api/v1/ui/dashboard/?period=30d")
        self.assertEqual(filtered_response.status_code, 200)
        filtered_payload = filtered_response.json()
        self.assertEqual(filtered_payload["filters"]["period"], "30d")
        filtered_shipments_card = next(
            card
            for card in filtered_payload["activity_cards"]
            if card["label"] == "Expeditions creees"
        )
        self.assertEqual(filtered_shipments_card["value"], 2)

    def test_ui_dashboard_exposes_low_stock_rows(self):
        low_stock_product = Product.objects.create(
            sku="UI-API-LOW-001",
            name="UI API Low Stock Product",
            brand="Medi",
            default_location=self.product.default_location,
            is_active=True,
            qr_code_image="qr_codes/test.png",
        )
        ProductLot.objects.create(
            product=low_stock_product,
            lot_code="LOT-LOW-CRITICAL",
            status=ProductLotStatus.AVAILABLE,
            quantity_on_hand=1,
            quantity_reserved=0,
            location=self.product.default_location,
        )

        response = self.staff_client.get("/api/v1/ui/dashboard/")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("low_stock_threshold", payload)
        self.assertIn("low_stock_rows", payload)
        self.assertGreater(payload["low_stock_threshold"], 0)
        self.assertTrue(
            any(row["sku"] == low_stock_product.sku for row in payload["low_stock_rows"])
        )

    def test_ui_dashboard_exposes_shipment_chart_rows(self):
        Shipment.objects.create(
            status=ShipmentStatus.SHIPPED,
            shipper_name=self.shipper_contact.name,
            shipper_contact_ref=self.shipper_contact,
            recipient_name=self.recipient_contact.name,
            recipient_contact_ref=self.recipient_contact,
            correspondent_name=self.correspondent_contact.name,
            correspondent_contact_ref=self.correspondent_contact,
            destination=self.destination,
            destination_address="14 Rue Chart",
            destination_country="France",
            created_by=self.staff_user,
        )

        response = self.staff_client.get("/api/v1/ui/dashboard/")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("shipments_total", payload)
        self.assertIn("shipment_chart_rows", payload)
        self.assertEqual(payload["shipments_total"], 2)
        self.assertEqual(
            sum(row["count"] for row in payload["shipment_chart_rows"]),
            payload["shipments_total"],
        )
        row_by_status = {
            row["status"]: row for row in payload["shipment_chart_rows"]
        }
        self.assertEqual(row_by_status[ShipmentStatus.PLANNED]["count"], 1)
        self.assertEqual(row_by_status[ShipmentStatus.SHIPPED]["count"], 1)

    def test_ui_dashboard_exposes_shipment_cards(self):
        Shipment.objects.create(
            status=ShipmentStatus.DRAFT,
            reference=f"{TEMP_SHIPMENT_REFERENCE_PREFIX}UI-001",
            shipper_name=self.shipper_contact.name,
            shipper_contact_ref=self.shipper_contact,
            recipient_name=self.recipient_contact.name,
            recipient_contact_ref=self.recipient_contact,
            correspondent_name=self.correspondent_contact.name,
            correspondent_contact_ref=self.correspondent_contact,
            destination=self.destination,
            destination_address="15 Rue Cards",
            destination_country="France",
            created_by=self.staff_user,
        )
        Shipment.objects.create(
            status=ShipmentStatus.PICKING,
            shipper_name=self.shipper_contact.name,
            shipper_contact_ref=self.shipper_contact,
            recipient_name=self.recipient_contact.name,
            recipient_contact_ref=self.recipient_contact,
            correspondent_name=self.correspondent_contact.name,
            correspondent_contact_ref=self.correspondent_contact,
            destination=self.destination,
            destination_address="16 Rue Cards",
            destination_country="France",
            created_by=self.staff_user,
        )
        Shipment.objects.create(
            status=ShipmentStatus.PACKED,
            shipper_name=self.shipper_contact.name,
            shipper_contact_ref=self.shipper_contact,
            recipient_name=self.recipient_contact.name,
            recipient_contact_ref=self.recipient_contact,
            correspondent_name=self.correspondent_contact.name,
            correspondent_contact_ref=self.correspondent_contact,
            destination=self.destination,
            destination_address="17 Rue Cards",
            destination_country="France",
            created_by=self.staff_user,
        )
        disputed_shipment = Shipment.objects.create(
            status=ShipmentStatus.PLANNED,
            is_disputed=True,
            shipper_name=self.shipper_contact.name,
            shipper_contact_ref=self.shipper_contact,
            recipient_name=self.recipient_contact.name,
            recipient_contact_ref=self.recipient_contact,
            correspondent_name=self.correspondent_contact.name,
            correspondent_contact_ref=self.correspondent_contact,
            destination=self.destination,
            destination_address="18 Rue Cards",
            destination_country="France",
            created_by=self.staff_user,
        )

        response = self.staff_client.get("/api/v1/ui/dashboard/")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("shipment_cards", payload)
        cards = {card["label"]: card for card in payload["shipment_cards"]}
        self.assertEqual(cards["Brouillons"]["value"], 1)
        self.assertEqual(cards["En cours"]["value"], 1)
        self.assertEqual(cards["Pretes"]["value"], 1)
        self.assertEqual(cards["En transit"]["value"], 2)
        self.assertEqual(cards["Litiges ouverts"]["value"], 1)
        self.assertEqual(cards["Brouillons"]["tone"], "warn")
        self.assertEqual(cards["Pretes"]["tone"], "success")
        self.assertEqual(cards["Litiges ouverts"]["tone"], "danger")

        ShipmentTrackingEvent.objects.create(
            shipment=disputed_shipment,
            status=ShipmentTrackingStatus.PLANNED,
            actor_name="Ops",
            actor_structure="ASF",
            comments="planned",
            created_by=self.staff_user,
        )
        refreshed = self.staff_client.get("/api/v1/ui/dashboard/").json()
        refreshed_cards = {card["label"]: card for card in refreshed["shipment_cards"]}
        self.assertEqual(refreshed_cards["Planifiees (semaine)"]["value"], 2)

    def test_ui_dashboard_exposes_carton_cards(self):
        secondary_destination = Destination.objects.create(
            city="TNR-CARTON-UI",
            iata_code="TNR-CARTON-UI",
            country="Madagascar",
            correspondent_contact=self.correspondent_contact,
            is_active=True,
        )
        secondary_shipment = Shipment.objects.create(
            status=ShipmentStatus.PLANNED,
            shipper_name=self.shipper_contact.name,
            shipper_contact_ref=self.shipper_contact,
            recipient_name=self.recipient_contact.name,
            recipient_contact_ref=self.recipient_contact,
            correspondent_name=self.correspondent_contact.name,
            correspondent_contact_ref=self.correspondent_contact,
            destination=secondary_destination,
            destination_address="19 Rue Cartons",
            destination_country="Madagascar",
            created_by=self.staff_user,
        )

        Carton.objects.create(code="UI-CARTON-PICKING", status=CartonStatus.PICKING)
        Carton.objects.create(code="UI-CARTON-ASSIGNED-RUN", status=CartonStatus.ASSIGNED, shipment=self.shipment)
        Carton.objects.create(code="UI-CARTON-ASSIGNED-TNR", status=CartonStatus.ASSIGNED, shipment=secondary_shipment)
        Carton.objects.create(code="UI-CARTON-LABELED-RUN", status=CartonStatus.LABELED, shipment=self.shipment)
        Carton.objects.create(code="UI-CARTON-LABELED-TNR", status=CartonStatus.LABELED, shipment=secondary_shipment)
        Carton.objects.create(code="UI-CARTON-SHIPPED-RUN", status=CartonStatus.SHIPPED, shipment=self.shipment)
        Carton.objects.create(code="UI-CARTON-SHIPPED-TNR", status=CartonStatus.SHIPPED, shipment=secondary_shipment)

        response = self.staff_client.get("/api/v1/ui/dashboard/")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("carton_cards", payload)
        cards = {card["label"]: card for card in payload["carton_cards"]}
        self.assertEqual(cards["En preparation"]["value"], 1)
        self.assertEqual(cards["Prets non affectes"]["value"], 2)
        self.assertEqual(cards["Affectes non etiquetes"]["value"], 2)
        self.assertEqual(cards["Etiquetes"]["value"], 2)
        self.assertEqual(cards["Colis expedies"]["value"], 2)
        self.assertEqual(cards["Prets non affectes"]["tone"], "warn")
        self.assertEqual(cards["Etiquetes"]["tone"], "success")

        filtered_response = self.staff_client.get(
            f"/api/v1/ui/dashboard/?destination={secondary_destination.id}"
        )
        self.assertEqual(filtered_response.status_code, 200)
        filtered_payload = filtered_response.json()
        filtered_cards = {
            card["label"]: card for card in filtered_payload["carton_cards"]
        }
        self.assertEqual(filtered_cards["En preparation"]["value"], 1)
        self.assertEqual(filtered_cards["Prets non affectes"]["value"], 2)
        self.assertEqual(filtered_cards["Affectes non etiquetes"]["value"], 1)
        self.assertEqual(filtered_cards["Etiquetes"]["value"], 1)
        self.assertEqual(filtered_cards["Colis expedies"]["value"], 1)

    def test_ui_stock_returns_products_and_filters(self):
        response = self.staff_client.get("/api/v1/ui/stock/?q=UI%20API")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["filters"]["q"], "UI API")
        self.assertEqual(payload["meta"]["total_products"], 1)
        self.assertEqual(payload["products"][0]["sku"], self.product.sku)

    def test_ui_cartons_returns_rows(self):
        response = self.staff_client.get("/api/v1/ui/cartons/")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("meta", payload)
        self.assertIn("cartons", payload)
        self.assertEqual(payload["meta"]["total_cartons"], 1)
        self.assertEqual(payload["cartons"][0]["code"], self.ready_carton.code)
        self.assertEqual(payload["cartons"][0]["packing_list"][0]["quantity"], 2)

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

    def test_ui_shipments_ready_returns_rows(self):
        response = self.staff_client.get("/api/v1/ui/shipments/ready/")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("meta", payload)
        self.assertIn("shipments", payload)
        self.assertEqual(payload["meta"]["total_shipments"], 1)
        self.assertEqual(payload["shipments"][0]["reference"], self.shipment.reference)
        self.assertIn("documents", payload["shipments"][0])
        self.assertIn("actions", payload["shipments"][0])
        self.assertIn(
            "return_to=shipments_ready",
            payload["shipments"][0]["actions"]["tracking_url"],
        )

    def test_ui_shipments_ready_archive_stale_drafts_archives_only_stale_temp_drafts(self):
        stale_draft = Shipment.objects.create(
            status=ShipmentStatus.DRAFT,
            reference=f"{TEMP_SHIPMENT_REFERENCE_PREFIX}88",
            shipper_name=self.shipper_contact.name,
            shipper_contact_ref=self.shipper_contact,
            recipient_name=self.recipient_contact.name,
            recipient_contact_ref=self.recipient_contact,
            correspondent_name=self.correspondent_contact.name,
            correspondent_contact_ref=self.correspondent_contact,
            destination=self.destination,
            destination_address="3 Rue Test",
            destination_country="France",
            created_by=self.staff_user,
        )
        recent_draft = Shipment.objects.create(
            status=ShipmentStatus.DRAFT,
            reference=f"{TEMP_SHIPMENT_REFERENCE_PREFIX}89",
            shipper_name=self.shipper_contact.name,
            shipper_contact_ref=self.shipper_contact,
            recipient_name=self.recipient_contact.name,
            recipient_contact_ref=self.recipient_contact,
            correspondent_name=self.correspondent_contact.name,
            correspondent_contact_ref=self.correspondent_contact,
            destination=self.destination,
            destination_address="4 Rue Test",
            destination_country="France",
            created_by=self.staff_user,
        )
        Shipment.objects.filter(pk=stale_draft.pk).update(
            created_at=timezone.now() - timedelta(days=40)
        )
        Shipment.objects.filter(pk=recent_draft.pk).update(
            created_at=timezone.now() - timedelta(days=2)
        )

        response = self.staff_client.post(
            "/api/v1/ui/shipments/ready/archive-stale-drafts/",
            {},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["archived_count"], 1)
        self.assertEqual(payload["stale_draft_count"], 0)

        stale_draft.refresh_from_db()
        recent_draft.refresh_from_db()
        self.assertIsNotNone(stale_draft.archived_at)
        self.assertIsNone(recent_draft.archived_at)

    def test_ui_shipments_tracking_returns_rows_and_filters(self):
        closed_shipment = Shipment.objects.create(
            status=ShipmentStatus.DELIVERED,
            shipper_name=self.shipper_contact.name,
            shipper_contact_ref=self.shipper_contact,
            recipient_name=self.recipient_contact.name,
            recipient_contact_ref=self.recipient_contact,
            correspondent_name=self.correspondent_contact.name,
            correspondent_contact_ref=self.correspondent_contact,
            destination=self.destination,
            destination_address="2 Rue Test",
            destination_country="France",
            created_by=self.staff_user,
            closed_at=self.shipment.created_at,
            closed_by=self.staff_user,
        )

        response_all = self.staff_client.get("/api/v1/ui/shipments/tracking/?closed=all")
        self.assertEqual(response_all.status_code, 200)
        payload_all = response_all.json()
        self.assertIn("meta", payload_all)
        self.assertIn("filters", payload_all)
        self.assertIn("warnings", payload_all)
        self.assertIn("shipments", payload_all)
        self.assertEqual(payload_all["filters"]["closed"], "all")
        self.assertEqual(payload_all["warnings"], [])
        self.assertEqual(payload_all["meta"]["total_shipments"], 2)
        self.assertEqual(
            {row["reference"] for row in payload_all["shipments"]},
            {self.shipment.reference, closed_shipment.reference},
        )

        tracked_row = next(
            row for row in payload_all["shipments"] if row["id"] == self.shipment.id
        )
        self.assertIn("actions", tracked_row)
        self.assertIn("tracking_url", tracked_row["actions"])
        self.assertIn(
            "return_to=shipments_tracking",
            tracked_row["actions"]["tracking_url"],
        )

        response_open = self.staff_client.get("/api/v1/ui/shipments/tracking/")
        self.assertEqual(response_open.status_code, 200)
        payload_open = response_open.json()
        self.assertEqual(payload_open["filters"]["closed"], "exclude")
        self.assertEqual(payload_open["meta"]["total_shipments"], 1)
        self.assertEqual(payload_open["shipments"][0]["reference"], self.shipment.reference)

    def test_ui_shipments_tracking_invalid_week_returns_warning(self):
        response = self.staff_client.get(
            "/api/v1/ui/shipments/tracking/?planned_week=invalid-week"
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["filters"]["planned_week"], "invalid-week")
        self.assertEqual(
            payload["warnings"],
            ["Format semaine invalide. Utilisez AAAA-Wss ou AAAA-ss."],
        )

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

    def test_ui_portal_order_create_success_for_association_user(self):
        response = self.portal_client.post(
            "/api/v1/ui/portal/orders/",
            {
                "destination_id": self.destination.id,
                "recipient_id": str(self.portal_recipient.id),
                "notes": "Besoin urgent",
                "lines": [{"product_id": self.product.id, "quantity": 2}],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertTrue(payload["ok"])
        created_order = Order.objects.get(pk=payload["order"]["id"])
        self.assertEqual(created_order.association_contact_id, self.portal_order.association_contact_id)
        self.assertEqual(created_order.lines.count(), 1)
        self.assertIsNotNone(created_order.shipment_id)

    def test_ui_portal_order_create_rejects_invalid_destination(self):
        response = self.portal_client.post(
            "/api/v1/ui/portal/orders/",
            {
                "destination_id": 999999,
                "recipient_id": str(self.portal_recipient.id),
                "lines": [{"product_id": self.product.id, "quantity": 1}],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "destination_invalid")

    def test_ui_portal_recipients_crud(self):
        list_response = self.portal_client.get("/api/v1/ui/portal/recipients/")
        self.assertEqual(list_response.status_code, 200)
        self.assertGreaterEqual(len(list_response.json()["recipients"]), 1)

        create_response = self.portal_client.post(
            "/api/v1/ui/portal/recipients/",
            {
                "destination_id": self.destination.id,
                "structure_name": "New Structure",
                "contact_title": AssociationContactTitle.MR,
                "contact_last_name": "Martin",
                "contact_first_name": "Luc",
                "phones": "0100000000",
                "emails": "luc.martin@example.org",
                "address_line1": "2 Rue Test",
                "postal_code": "75002",
                "city": "Paris",
                "country": "France",
                "notify_deliveries": True,
                "is_delivery_contact": True,
            },
            format="json",
        )
        self.assertEqual(create_response.status_code, 201)
        recipient_id = create_response.json()["recipient"]["id"]

        patch_response = self.portal_client.patch(
            f"/api/v1/ui/portal/recipients/{recipient_id}/",
            {
                "destination_id": self.destination.id,
                "structure_name": "New Structure Updated",
                "contact_title": AssociationContactTitle.MRS,
                "contact_last_name": "Martin",
                "contact_first_name": "Lucie",
                "phones": "0100000001",
                "emails": "lucie.martin@example.org",
                "address_line1": "3 Rue Test",
                "postal_code": "75003",
                "city": "Paris",
                "country": "France",
                "notify_deliveries": True,
                "is_delivery_contact": False,
            },
            format="json",
        )
        self.assertEqual(patch_response.status_code, 200)
        self.assertEqual(
            patch_response.json()["recipient"]["structure_name"],
            "New Structure Updated",
        )

    def test_ui_portal_account_patch_updates_profile(self):
        response = self.portal_client.patch(
            "/api/v1/ui/portal/account/",
            {
                "association_name": "Association UI API Updated",
                "association_email": "new-assoc@example.org",
                "association_phone": "0203040506",
                "address_line1": "10 Rue Assoc",
                "address_line2": "",
                "postal_code": "69001",
                "city": "Lyon",
                "country": "France",
                "contacts": [
                    {
                        "title": AssociationContactTitle.MR,
                        "last_name": "Admin",
                        "first_name": "Portal",
                        "phone": "0600000000",
                        "email": "portal.admin@example.org",
                        "is_administrative": True,
                        "is_shipping": False,
                        "is_billing": False,
                    }
                ],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["account"]["association_name"], "Association UI API Updated")
        self.assertEqual(len(payload["account"]["portal_contacts"]), 1)

    def test_ui_portal_account_patch_rejects_contact_without_type(self):
        response = self.portal_client.patch(
            "/api/v1/ui/portal/account/",
            {
                "association_name": "Association UI API",
                "association_email": "assoc@example.org",
                "association_phone": "0102030405",
                "address_line1": "10 Rue Assoc",
                "postal_code": "69001",
                "city": "Lyon",
                "country": "France",
                "contacts": [
                    {
                        "title": AssociationContactTitle.MR,
                        "last_name": "Admin",
                        "first_name": "Portal",
                        "phone": "0600000000",
                        "email": "portal.admin@example.org",
                        "is_administrative": False,
                        "is_shipping": False,
                        "is_billing": False,
                    }
                ],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "contact_rows_invalid")

    def test_ui_shipment_documents_upload_delete_and_permissions(self):
        forbidden = self.basic_client.get(f"/api/v1/ui/shipments/{self.shipment.id}/documents/")
        self.assertEqual(forbidden.status_code, 403)

        list_response = self.staff_client.get(f"/api/v1/ui/shipments/{self.shipment.id}/documents/")
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.json()["additional_documents"], [])

        uploaded_file = SimpleUploadedFile(
            "manifest.pdf",
            b"%PDF-1.4 test",
            content_type="application/pdf",
        )
        upload_response = self.staff_client.post(
            f"/api/v1/ui/shipments/{self.shipment.id}/documents/",
            {"document_file": uploaded_file},
            format="multipart",
        )
        self.assertEqual(upload_response.status_code, 201)
        doc_id = upload_response.json()["document"]["id"]
        self.assertTrue(
            Document.objects.filter(
                id=doc_id,
                shipment_id=self.shipment.id,
                doc_type=DocumentType.ADDITIONAL,
            ).exists()
        )

        refreshed_list = self.staff_client.get(f"/api/v1/ui/shipments/{self.shipment.id}/documents/")
        self.assertEqual(refreshed_list.status_code, 200)
        additional_ids = [doc["id"] for doc in refreshed_list.json()["additional_documents"]]
        self.assertIn(doc_id, additional_ids)

        delete_response = self.staff_client.delete(
            f"/api/v1/ui/shipments/{self.shipment.id}/documents/{doc_id}/",
            format="json",
        )
        self.assertEqual(delete_response.status_code, 200)
        self.assertFalse(Document.objects.filter(id=doc_id).exists())

    def test_ui_shipment_labels_endpoints_return_urls(self):
        carton_a = Carton.objects.create(
            code="UI-LABEL-A",
            status=CartonStatus.ASSIGNED,
            shipment=self.shipment,
        )
        carton_b = Carton.objects.create(
            code="UI-LABEL-B",
            status=CartonStatus.LABELED,
            shipment=self.shipment,
        )

        list_response = self.staff_client.get(f"/api/v1/ui/shipments/{self.shipment.id}/labels/")
        self.assertEqual(list_response.status_code, 200)
        payload = list_response.json()
        self.assertIn("/scan/shipment/", payload["all_url"])
        self.assertEqual(len(payload["labels"]), 2)

        detail_response = self.staff_client.get(
            f"/api/v1/ui/shipments/{self.shipment.id}/labels/{carton_a.id}/"
        )
        self.assertEqual(detail_response.status_code, 200)
        self.assertIn(f"/scan/shipment/{self.shipment.id}/labels/{carton_a.id}/", detail_response.json()["url"])

        missing_response = self.staff_client.get(
            f"/api/v1/ui/shipments/{self.shipment.id}/labels/{self.available_carton.id}/"
        )
        self.assertEqual(missing_response.status_code, 404)
        self.assertEqual(missing_response.json()["code"], "carton_not_found")

        self.assertNotEqual(carton_a.id, carton_b.id)

    def test_ui_templates_require_superuser(self):
        forbidden = self.staff_client.get("/api/v1/ui/templates/")
        self.assertEqual(forbidden.status_code, 403)
        self.assertEqual(forbidden.json()["code"], "superuser_required")

        allowed = self.superuser_client.get("/api/v1/ui/templates/")
        self.assertEqual(allowed.status_code, 200)
        self.assertGreaterEqual(len(allowed.json()["templates"]), 1)

    def test_ui_template_detail_patch_and_reset(self):
        detail_response = self.superuser_client.get("/api/v1/ui/templates/shipment_note/")
        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(detail_response.json()["doc_type"], "shipment_note")

        save_response = self.superuser_client.patch(
            "/api/v1/ui/templates/shipment_note/",
            {
                "action": "save",
                "layout": {
                    "blocks": [
                        {"id": "text-1", "type": "text", "text": "template custom"}
                    ]
                },
            },
            format="json",
        )
        self.assertEqual(save_response.status_code, 200)
        self.assertTrue(save_response.json()["changed"])
        template = PrintTemplate.objects.get(doc_type="shipment_note")
        self.assertEqual(template.versions.count(), 1)
        self.assertTrue(template.layout)

        same_layout_response = self.superuser_client.patch(
            "/api/v1/ui/templates/shipment_note/",
            {
                "action": "save",
                "layout": {
                    "blocks": [
                        {"id": "text-1", "type": "text", "text": "template custom"}
                    ]
                },
            },
            format="json",
        )
        self.assertEqual(same_layout_response.status_code, 200)
        self.assertFalse(same_layout_response.json()["changed"])

        reset_response = self.superuser_client.patch(
            "/api/v1/ui/templates/shipment_note/",
            {
                "action": "reset",
                "layout": {},
            },
            format="json",
        )
        self.assertEqual(reset_response.status_code, 200)
        self.assertTrue(reset_response.json()["changed"])

        template.refresh_from_db()
        self.assertEqual(template.layout, {})
        self.assertEqual(
            PrintTemplateVersion.objects.filter(template=template).count(),
            2,
        )

    def test_ui_scan_role_matrix_allows_staff_roles_and_blocks_non_staff(self):
        checks = [
            ("get", "/api/v1/ui/dashboard/", None, "json"),
            ("get", "/api/v1/ui/cartons/", None, "json"),
            ("get", "/api/v1/ui/stock/", None, "json"),
            ("get", "/api/v1/ui/shipments/form-options/", None, "json"),
            ("get", "/api/v1/ui/shipments/ready/", None, "json"),
            ("get", "/api/v1/ui/shipments/tracking/", None, "json"),
            ("get", f"/api/v1/ui/shipments/{self.shipment.id}/documents/", None, "json"),
            ("get", f"/api/v1/ui/shipments/{self.shipment.id}/labels/", None, "json"),
            (
                "post",
                "/api/v1/ui/stock/update/",
                {
                    "product_code": self.product.sku,
                    "quantity": 0,
                    "expires_on": "2026-12-31",
                },
                "json",
            ),
            (
                "post",
                "/api/v1/ui/stock/out/",
                {
                    "product_code": self.product.sku,
                    "quantity": 0,
                },
                "json",
            ),
            (
                "post",
                "/api/v1/ui/shipments/ready/archive-stale-drafts/",
                {},
                "json",
            ),
            (
                "post",
                "/api/v1/ui/shipments/",
                self._shipment_mutation_payload(
                    lines=[{"product_code": self.product.sku}]
                ),
                "json",
            ),
            (
                "patch",
                f"/api/v1/ui/shipments/{self.shipment.id}/",
                self._shipment_mutation_payload(
                    lines=[{"carton_id": self.available_carton.id}]
                ),
                "json",
            ),
            (
                "post",
                f"/api/v1/ui/shipments/{self.shipment.id}/tracking-events/",
                {},
                "json",
            ),
            (
                "post",
                f"/api/v1/ui/shipments/{self.shipment.id}/close/",
                {},
                "json",
            ),
            (
                "post",
                f"/api/v1/ui/shipments/{self.shipment.id}/documents/",
                {},
                "multipart",
            ),
            (
                "delete",
                f"/api/v1/ui/shipments/{self.shipment.id}/documents/999999/",
                None,
                "json",
            ),
        ]
        for method, path, payload, fmt in checks:
            for role_name, client in self.staff_role_clients.items():
                response = self._call_endpoint(
                    client,
                    method,
                    path,
                    payload=payload,
                    fmt=fmt,
                )
                self.assertNotEqual(
                    response.status_code,
                    403,
                    msg=f"{role_name} unexpectedly forbidden on {method} {path}",
                )
            for role_name in ("basic", "portal"):
                response = self._call_endpoint(
                    self.role_clients[role_name],
                    method,
                    path,
                    payload=payload,
                    fmt=fmt,
                )
                self.assertEqual(
                    response.status_code,
                    403,
                    msg=f"{role_name} should be forbidden on {method} {path}",
                )

    def test_ui_templates_role_matrix_requires_superuser(self):
        for role_name in (
            "staff",
            "admin",
            "qualite",
            "magasinier",
            "benevole",
            "livreur",
            "basic",
            "portal",
        ):
            response = self.role_clients[role_name].get("/api/v1/ui/templates/")
            self.assertEqual(response.status_code, 403, msg=role_name)
        allowed = self.superuser_client.get("/api/v1/ui/templates/")
        self.assertEqual(allowed.status_code, 200)

    def test_ui_portal_role_matrix_allows_association_profile_only(self):
        checks = [
            ("get", "/api/v1/ui/portal/dashboard/", None, "json"),
            ("get", "/api/v1/ui/portal/recipients/", None, "json"),
            ("get", "/api/v1/ui/portal/account/", None, "json"),
            (
                "post",
                "/api/v1/ui/portal/orders/",
                {
                    "destination_id": 999999,
                    "recipient_id": str(self.portal_recipient.id),
                    "lines": [{"product_id": self.product.id, "quantity": 1}],
                },
                "json",
            ),
        ]
        for method, path, payload, fmt in checks:
            response = self._call_endpoint(
                self.portal_client,
                method,
                path,
                payload=payload,
                fmt=fmt,
            )
            self.assertNotEqual(
                response.status_code,
                403,
                msg=f"portal user unexpectedly forbidden on {method} {path}",
            )
            for role_name, client in self.staff_role_clients.items():
                forbidden = self._call_endpoint(
                    client,
                    method,
                    path,
                    payload=payload,
                    fmt=fmt,
                )
                self.assertEqual(
                    forbidden.status_code,
                    403,
                    msg=f"{role_name} should be forbidden on {method} {path}",
                )
            basic_forbidden = self._call_endpoint(
                self.basic_client,
                method,
                path,
                payload=payload,
                fmt=fmt,
            )
            self.assertEqual(basic_forbidden.status_code, 403)

    def test_ui_document_mutations_emit_workflow_audit_events(self):
        with mock.patch("api.v1.ui_views.log_workflow_event", create=True) as log_mock:
            upload_response = self.staff_client.post(
                f"/api/v1/ui/shipments/{self.shipment.id}/documents/",
                {
                    "document_file": SimpleUploadedFile(
                        "audit-manifest.pdf",
                        b"%PDF-1.4 audit",
                        content_type="application/pdf",
                    )
                },
                format="multipart",
            )
            self.assertEqual(upload_response.status_code, 201)
            document_id = upload_response.json()["document"]["id"]
            delete_response = self.staff_client.delete(
                f"/api/v1/ui/shipments/{self.shipment.id}/documents/{document_id}/",
                format="json",
            )
            self.assertEqual(delete_response.status_code, 200)
        event_types = [call.args[0] for call in log_mock.call_args_list]
        self.assertIn("ui_shipment_document_uploaded", event_types)
        self.assertIn("ui_shipment_document_deleted", event_types)

    def test_ui_portal_mutations_emit_workflow_audit_events(self):
        with mock.patch("api.v1.ui_views.log_workflow_event", create=True) as log_mock:
            order_response = self.portal_client.post(
                "/api/v1/ui/portal/orders/",
                {
                    "destination_id": self.destination.id,
                    "recipient_id": str(self.portal_recipient.id),
                    "notes": "Audit event order",
                    "lines": [{"product_id": self.product.id, "quantity": 1}],
                },
                format="json",
            )
            self.assertEqual(order_response.status_code, 201)

            create_recipient_response = self.portal_client.post(
                "/api/v1/ui/portal/recipients/",
                {
                    "destination_id": self.destination.id,
                    "structure_name": "Audit Recipient",
                    "contact_title": AssociationContactTitle.MR,
                    "contact_last_name": "Audit",
                    "contact_first_name": "Test",
                    "phones": "0100000000",
                    "emails": "audit.recipient@example.org",
                    "address_line1": "12 Rue Audit",
                    "postal_code": "75001",
                    "city": "Paris",
                    "country": "France",
                    "notify_deliveries": True,
                    "is_delivery_contact": True,
                },
                format="json",
            )
            self.assertEqual(create_recipient_response.status_code, 201)
            created_recipient_id = create_recipient_response.json()["recipient"]["id"]

            patch_recipient_response = self.portal_client.patch(
                f"/api/v1/ui/portal/recipients/{created_recipient_id}/",
                {
                    "destination_id": self.destination.id,
                    "structure_name": "Audit Recipient Updated",
                    "contact_title": AssociationContactTitle.MRS,
                    "contact_last_name": "Audit",
                    "contact_first_name": "Tester",
                    "phones": "0100000001",
                    "emails": "audit.updated@example.org",
                    "address_line1": "13 Rue Audit",
                    "postal_code": "75002",
                    "city": "Paris",
                    "country": "France",
                    "notify_deliveries": True,
                    "is_delivery_contact": False,
                },
                format="json",
            )
            self.assertEqual(patch_recipient_response.status_code, 200)

            account_response = self.portal_client.patch(
                "/api/v1/ui/portal/account/",
                {
                    "association_name": "Association UI API Audit",
                    "association_email": "audit-assoc@example.org",
                    "association_phone": "0203040506",
                    "address_line1": "10 Rue Assoc",
                    "address_line2": "",
                    "postal_code": "69001",
                    "city": "Lyon",
                    "country": "France",
                    "contacts": [
                        {
                            "title": AssociationContactTitle.MR,
                            "last_name": "Audit",
                            "first_name": "Admin",
                            "phone": "0600000000",
                            "email": "audit.portal.admin@example.org",
                            "is_administrative": True,
                            "is_shipping": False,
                            "is_billing": False,
                        }
                    ],
                },
                format="json",
            )
            self.assertEqual(account_response.status_code, 200)

        event_types = [call.args[0] for call in log_mock.call_args_list]
        self.assertIn("ui_portal_order_created", event_types)
        self.assertIn("ui_portal_recipient_created", event_types)
        self.assertIn("ui_portal_recipient_updated", event_types)
        self.assertIn("ui_portal_account_updated", event_types)
