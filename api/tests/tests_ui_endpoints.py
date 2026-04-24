from datetime import date, datetime, timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db.models import Sum
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from contacts.capabilities import ContactCapabilityType
from contacts.models import Contact, ContactType
from wms.application.parties.use_cases import (
    update_recipient_shared_profile,
)
from wms.application.portal.dashboard_queries import build_portal_dashboard_payload
from wms.application.scan.dashboard_queries import build_scan_dashboard_payload
from wms.models import (
    TEMP_SHIPMENT_REFERENCE_PREFIX,
    AssociationContactTitle,
    AssociationProfile,
    AssociationRecipient,
    Carton,
    CartonItem,
    CartonStatus,
    Destination,
    Document,
    DocumentType,
    GeneratedPrintArtifact,
    GeneratedPrintArtifactStatus,
    IntegrationDirection,
    IntegrationEvent,
    IntegrationStatus,
    Location,
    OpsEscalation,
    OpsPilotageSnapshot,
    Order,
    OrderReviewStatus,
    PortalAccessGrant,
    PortalAccessRole,
    PrintTemplate,
    PrintTemplateVersion,
    Product,
    ProductLot,
    ProductLotStatus,
    Receipt,
    ReceiptStatus,
    ReceiptType,
    Shipment,
    ShipmentAuthorizedRecipientContact,
    ShipmentRecipientContact,
    ShipmentRecipientOrganization,
    ShipmentShipper,
    ShipmentShipperRecipientLink,
    ShipmentStatus,
    ShipmentTrackingEvent,
    ShipmentTrackingProofMode,
    ShipmentTrackingStatus,
    ShipmentValidationStatus,
    ShipmentWorkflowProjection,
    Warehouse,
    WorkflowBlockageClaim,
)
from wms.portal_recipient_sync import sync_association_recipient_to_contact


class UiApiEndpointsTests(TestCase):
    DASHBOARD_QUERY_ONLY_KEYS = {
        "workflow_blockage_base_rows",
        "shipments_scope",
        "shipments_with_tracking",
        "status_map",
        "stock_snapshot",
        "email_queue_snapshot",
        "document_scan_snapshot",
        "workflow_blockage_snapshot",
        "period_start",
        "week_start",
        "week_end",
    }

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        user_model = get_user_model()
        cls.staff_user = user_model.objects.create_user(
            username="ui-api-staff",
            password="pass1234",
            is_staff=True,
        )
        cls.basic_user = user_model.objects.create_user(
            username="ui-api-basic",
            password="pass1234",
        )
        cls.portal_user = user_model.objects.create_user(
            username="ui-api-portal",
            password="pass1234",
        )
        cls.recipient_scope_user = user_model.objects.create_user(
            username="ui-api-recipient-scope",
            password="pass1234",
        )
        cls.superuser_user = user_model.objects.create_user(
            username="ui-api-superuser",
            password="pass1234",
            is_staff=True,
            is_superuser=True,
        )

        cls.association_contact = Contact.objects.create(
            name="Association UI API",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        AssociationProfile.objects.create(
            user=cls.portal_user,
            contact=cls.association_contact,
        )

        cls.role_users = {
            "staff": cls.staff_user,
            "superuser": cls.superuser_user,
            "basic": cls.basic_user,
            "portal": cls.portal_user,
        }
        for role_name in ("admin", "qualite", "magasinier", "benevole", "livreur"):
            cls.role_users[role_name] = user_model.objects.create_user(
                username=f"ui-api-{role_name}",
                password="pass1234",
                is_staff=True,
            )

        warehouse = Warehouse.objects.create(name="UI API WH", code="UIA")
        location = Location.objects.create(
            warehouse=warehouse,
            zone="A",
            aisle="01",
            shelf="001",
        )
        cls.product = Product.objects.create(
            sku="UI-API-001",
            name="UI API Product",
            brand="Medi",
            default_location=location,
            is_active=True,
            qr_code_image="qr_codes/test.png",
        )
        cls.product_lot = ProductLot.objects.create(
            product=cls.product,
            lot_code="LOT-LOW",
            status=ProductLotStatus.AVAILABLE,
            quantity_on_hand=15,
            quantity_reserved=0,
            location=location,
        )

        cls.correspondent_contact = cls._create_contact(
            "UI Correspondent",
            contact_type=ContactType.PERSON,
        )
        cls.correspondent_org = cls._create_contact("UI Correspondent Org")
        cls.correspondent_contact.organization = cls.correspondent_org
        cls.correspondent_contact.save(update_fields=["organization"])
        cls.destination = Destination.objects.create(
            city="RUN",
            iata_code="RUN",
            country="France",
            correspondent_contact=cls.correspondent_contact,
            is_active=True,
        )
        ShipmentRecipientOrganization.objects.create(
            organization=cls.correspondent_org,
            destination=cls.destination,
            validation_status=ShipmentValidationStatus.VALIDATED,
            is_correspondent=True,
            is_active=True,
        )

        cls.shipper_contact = cls._create_contact(
            "UI Shipper",
        )
        cls.shipper_referent = cls._create_contact(
            "UI Shipper Referent",
            contact_type=ContactType.PERSON,
        )
        cls.shipper_referent.organization = cls.shipper_contact
        cls.shipper_referent.save(update_fields=["organization"])
        cls.shipment_shipper = cls._ensure_shipment_shipper(
            cls.shipper_contact,
            default_contact=cls.shipper_referent,
        )

        cls.recipient_contact = cls._create_contact(
            "UI Recipient",
        )
        cls.recipient_referent = cls._create_contact(
            "UI Recipient Referent",
            contact_type=ContactType.PERSON,
        )
        cls.recipient_referent.organization = cls.recipient_contact
        cls.recipient_referent.save(update_fields=["organization"])
        (
            cls.shipment_recipient_organization,
            cls.shipment_recipient_contact,
            shipment_link,
        ) = cls._bind_recipient(
            cls.shipper_contact,
            cls.recipient_contact,
            cls.destination,
            recipient_referent=cls.recipient_referent,
        )

        cls.donor_contact = cls._create_contact(
            "UI Donor",
        )
        cls.donor_contact.capabilities.update_or_create(
            capability=ContactCapabilityType.DONOR,
            defaults={"is_active": True},
        )

        cls.available_carton = Carton.objects.create(
            code="UI-CARTON-AVAILABLE",
            status=CartonStatus.PACKED,
        )
        cls.ready_carton = Carton.objects.create(
            code="UI-CARTON-READY",
            status=CartonStatus.PACKED,
        )
        CartonItem.objects.create(
            carton=cls.ready_carton,
            product_lot=cls.product_lot,
            quantity=2,
        )

        cls.shipment = Shipment.objects.create(
            status=ShipmentStatus.PLANNED,
            shipper_name="ASF Hub",
            shipper_contact_ref=cls.shipper_contact,
            recipient_name="CHU Nord",
            recipient_contact_ref=cls.recipient_contact,
            correspondent_name="M. Dupont",
            correspondent_contact_ref=cls.correspondent_contact,
            destination=cls.destination,
            destination_address="1 Rue Test",
            destination_country="France",
            created_by=cls.staff_user,
        )
        ShipmentTrackingEvent.objects.create(
            shipment=cls.shipment,
            status=ShipmentTrackingStatus.PLANNED,
            comments="Planned",
            created_by=cls.staff_user,
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
            created_by=cls.staff_user,
        )
        cls.portal_order = Order.objects.create(
            association_contact=cls.association_contact,
            review_status=OrderReviewStatus.PENDING,
            shipper_name="Sender",
            recipient_name="Recipient",
            correspondent_name="Correspondent",
            destination_address="20 Rue Test",
            destination_country="France",
            created_by=cls.staff_user,
        )
        cls.portal_recipient = AssociationRecipient.objects.create(
            association_contact=cls.association_contact,
            destination=cls.destination,
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
        sync_association_recipient_to_contact(cls.portal_recipient)
        ShipmentRecipientOrganization.objects.filter(
            organization=cls.portal_recipient.synced_contact,
        ).update(validation_status=ShipmentValidationStatus.VALIDATED)
        PortalAccessGrant.objects.create(
            user=cls.recipient_scope_user,
            role=PortalAccessRole.RECIPIENT_ADMIN,
            recipient_organization=cls.shipment_recipient_organization,
        )

    def setUp(self):
        self.staff_client = APIClient()
        self.staff_client.force_authenticate(self.staff_user)
        self.basic_client = APIClient()
        self.basic_client.force_authenticate(self.basic_user)
        self.portal_client = APIClient()
        self.portal_client.force_authenticate(self.portal_user)
        self.recipient_scope_client = APIClient()
        self.recipient_scope_client.force_authenticate(self.recipient_scope_user)
        self.superuser_client = APIClient()
        self.superuser_client.force_authenticate(self.superuser_user)
        self.role_clients = {
            "staff": self.staff_client,
            "superuser": self.superuser_client,
            "basic": self.basic_client,
            "portal": self.portal_client,
        }
        for role_name in ("admin", "qualite", "magasinier", "benevole", "livreur"):
            role_client = APIClient()
            role_client.force_authenticate(self.role_users[role_name])
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

    @classmethod
    def _create_contact(cls, name, *, contact_type=ContactType.ORGANIZATION):
        contact = Contact.objects.create(
            name=name,
            contact_type=contact_type,
            is_active=True,
        )
        return contact

    def _create_delayed_dashboard_shipment(
        self,
        *,
        reference,
        shipment_status,
        tracking_status,
        hours_ago,
    ):
        shipment = Shipment.objects.create(
            reference=reference,
            status=shipment_status,
            shipper_name=self.shipper_contact.name,
            shipper_contact_ref=self.shipper_contact,
            recipient_name=self.recipient_contact.name,
            recipient_contact_ref=self.recipient_contact,
            correspondent_name=self.correspondent_contact.name,
            correspondent_contact_ref=self.correspondent_contact,
            destination=self.destination,
            destination_address="99 Rue SLA",
            destination_country="France",
            created_by=self.staff_user,
        )
        event = ShipmentTrackingEvent.objects.create(
            shipment=shipment,
            status=tracking_status,
            comments="delayed",
            created_by=self.staff_user,
            actor_name="Ops",
            actor_structure="ASF",
        )
        ShipmentTrackingEvent.objects.filter(pk=event.pk).update(
            created_at=timezone.now() - timedelta(hours=hours_ago)
        )
        shipment.refresh_from_db()
        return shipment

    def _create_workflow_projection(
        self,
        *,
        reference,
        destination,
        shipment_status=ShipmentStatus.PLANNED,
        current_segment="planned_to_boarding",
        delay_state="on_time",
        has_open_dispute=False,
        is_closed=False,
        active_blockage_category="",
        segment_age_hours=0.0,
        lead_hours_total_to_delivery=None,
        lead_hours_delivery_to_close=None,
        planned_at=None,
        projected_at=None,
    ):
        shipment = Shipment.objects.create(
            reference=reference,
            status=shipment_status,
            shipper_name=self.shipper_contact.name,
            shipper_contact_ref=self.shipper_contact,
            recipient_name=self.recipient_contact.name,
            recipient_contact_ref=self.recipient_contact,
            correspondent_name=self.correspondent_contact.name,
            correspondent_contact_ref=self.correspondent_contact,
            destination=destination,
            destination_address=f"{destination.city} Projection",
            destination_country=destination.country,
            created_by=self.staff_user,
            is_disputed=has_open_dispute,
        )
        started_at = timezone.now() - timedelta(hours=segment_age_hours)
        return ShipmentWorkflowProjection.objects.create(
            shipment=shipment,
            destination=destination,
            reference=shipment.reference,
            tracking_token=shipment.tracking_token,
            destination_label=str(destination),
            shipment_status=shipment_status,
            planned_at=planned_at,
            current_segment=current_segment,
            segment_started_at=started_at,
            segment_age_hours=segment_age_hours,
            is_closed=is_closed,
            has_open_dispute=has_open_dispute,
            delay_state=delay_state,
            active_blockage_category=active_blockage_category,
            lead_hours_total_to_delivery=lead_hours_total_to_delivery,
            lead_hours_delivery_to_close=lead_hours_delivery_to_close,
            projected_at=projected_at or timezone.now(),
        )

    @classmethod
    def _ensure_shipment_shipper(cls, shipper_contact, *, default_contact=None):
        if default_contact is None:
            default_contact = (
                Contact.objects.filter(
                    organization=shipper_contact,
                    contact_type=ContactType.PERSON,
                    is_active=True,
                )
                .order_by("id")
                .first()
            )
        if default_contact is None:
            default_contact = cls._create_contact(
                f"{shipper_contact.name} Referent",
                contact_type=ContactType.PERSON,
            )
            default_contact.organization = shipper_contact
            default_contact.save(update_fields=["organization"])
        shipper, _created = ShipmentShipper.objects.update_or_create(
            organization=shipper_contact,
            defaults={
                "default_contact": default_contact,
                "validation_status": ShipmentValidationStatus.VALIDATED,
                "is_active": True,
            },
        )
        return shipper

    @classmethod
    def _bind_recipient(
        cls,
        shipper_contact,
        recipient_contact,
        destination,
        *,
        recipient_referent=None,
    ):
        shipper = cls._ensure_shipment_shipper(shipper_contact)
        recipient_organization, _created = ShipmentRecipientOrganization.objects.update_or_create(
            organization=recipient_contact,
            defaults={
                "destination": destination,
                "validation_status": ShipmentValidationStatus.VALIDATED,
                "is_active": True,
            },
        )
        if recipient_referent is None:
            recipient_referent = cls._create_contact(
                f"{recipient_contact.name} Referent",
                contact_type=ContactType.PERSON,
            )
            recipient_referent.organization = recipient_contact
            recipient_referent.save(update_fields=["organization"])
        shipment_recipient_contact, _created = ShipmentRecipientContact.objects.update_or_create(
            recipient_organization=recipient_organization,
            contact=recipient_referent,
            defaults={"is_active": True},
        )
        shipment_link, _created = ShipmentShipperRecipientLink.objects.update_or_create(
            shipper=shipper,
            recipient_organization=recipient_organization,
            defaults={"is_active": True},
        )
        ShipmentAuthorizedRecipientContact.objects.update_or_create(
            link=shipment_link,
            recipient_contact=shipment_recipient_contact,
            defaults={"is_default": True, "is_active": True},
        )
        return recipient_organization, shipment_recipient_contact, shipment_link

    def _shipment_mutation_payload(self, *, lines):
        return {
            "destination": self.destination.id,
            "shipper_contact": self.shipper_referent.id,
            "recipient_contact": self.recipient_referent.id,
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
        self._create_workflow_projection(
            reference="EXP-UI-FILTER-RUN",
            destination=self.destination,
            delay_state="persistent",
            has_open_dispute=True,
            active_blockage_category="creation_expedition",
            segment_age_hours=48,
        )
        self._create_workflow_projection(
            reference="EXP-UI-FILTER-TNR",
            destination=secondary_destination,
            delay_state="critical",
            has_open_dispute=True,
            active_blockage_category="suivi",
            segment_age_hours=96,
        )

        response = self.staff_client.get("/api/v1/ui/dashboard/")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("filters", payload)
        self.assertIn("destinations", payload["filters"])
        destination_ids = {row["id"] for row in payload["filters"]["destinations"]}
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
        self.assertEqual(filtered_payload["kpis"]["open_shipments"], 2)
        self.assertEqual(len(filtered_payload["destination_risk_rows"]), 1)
        self.assertEqual(
            filtered_payload["destination_risk_rows"][0]["destination_id"],
            secondary_destination.id,
        )

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
        period_values = {row["value"] for row in payload["filters"]["period_choices"]}
        self.assertSetEqual(period_values, {"today", "7d", "30d", "week"})
        shipments_card = next(
            card for card in payload["activity_cards"] if card["label"] == "Expeditions creees"
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
        row_by_status = {row["status"]: row for row in payload["shipment_chart_rows"]}
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
        Carton.objects.create(
            code="UI-CARTON-ASSIGNED-RUN", status=CartonStatus.ASSIGNED, shipment=self.shipment
        )
        Carton.objects.create(
            code="UI-CARTON-ASSIGNED-TNR", status=CartonStatus.ASSIGNED, shipment=secondary_shipment
        )
        Carton.objects.create(
            code="UI-CARTON-LABELED-RUN", status=CartonStatus.LABELED, shipment=self.shipment
        )
        Carton.objects.create(
            code="UI-CARTON-LABELED-TNR", status=CartonStatus.LABELED, shipment=secondary_shipment
        )
        Carton.objects.create(
            code="UI-CARTON-SHIPPED-RUN", status=CartonStatus.SHIPPED, shipment=self.shipment
        )
        Carton.objects.create(
            code="UI-CARTON-SHIPPED-TNR", status=CartonStatus.SHIPPED, shipment=secondary_shipment
        )

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
        filtered_cards = {card["label"]: card for card in filtered_payload["carton_cards"]}
        self.assertEqual(filtered_cards["En preparation"]["value"], 1)
        self.assertEqual(filtered_cards["Prets non affectes"]["value"], 2)
        self.assertEqual(filtered_cards["Affectes non etiquetes"]["value"], 1)
        self.assertEqual(filtered_cards["Etiquetes"]["value"], 1)
        self.assertEqual(filtered_cards["Colis expedies"]["value"], 1)

    def test_ui_dashboard_exposes_flow_cards(self):
        Receipt.objects.create(
            receipt_type=ReceiptType.DONATION,
            status=ReceiptStatus.DRAFT,
            warehouse=self.product.default_location.warehouse,
            created_by=self.staff_user,
        )
        Order.objects.create(
            review_status=OrderReviewStatus.CHANGES_REQUESTED,
            shipper_name="Sender CR",
            recipient_name="Recipient CR",
            correspondent_name="Correspondent CR",
            destination_address="21 Rue Flow",
            destination_country="France",
            created_by=self.staff_user,
        )
        Order.objects.create(
            review_status=OrderReviewStatus.APPROVED,
            shipper_name="Sender AP",
            recipient_name="Recipient AP",
            correspondent_name="Correspondent AP",
            destination_address="22 Rue Flow",
            destination_country="France",
            created_by=self.staff_user,
        )

        response = self.staff_client.get("/api/v1/ui/dashboard/")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("flow_cards", payload)
        cards = {card["label"]: card for card in payload["flow_cards"]}
        self.assertEqual(
            cards["Receptions en attente"]["value"],
            Receipt.objects.filter(status=ReceiptStatus.DRAFT).count(),
        )
        self.assertEqual(
            cards["Cmd en attente de validation"]["value"],
            Order.objects.filter(review_status=OrderReviewStatus.PENDING).count(),
        )
        self.assertEqual(
            cards["Cmd a modifier"]["value"],
            Order.objects.filter(review_status=OrderReviewStatus.CHANGES_REQUESTED).count(),
        )
        self.assertEqual(
            cards["Cmd validees sans expedition"]["value"],
            Order.objects.filter(
                review_status=OrderReviewStatus.APPROVED,
                shipment__isnull=True,
            ).count(),
        )
        self.assertEqual(cards["Receptions en attente"]["tone"], "warn")
        self.assertEqual(cards["Cmd a modifier"]["tone"], "warn")

    def test_ui_dashboard_exposes_tracking_cards(self):
        planned_alert_shipment = Shipment.objects.create(
            status=ShipmentStatus.PLANNED,
            shipper_name=self.shipper_contact.name,
            shipper_contact_ref=self.shipper_contact,
            recipient_name=self.recipient_contact.name,
            recipient_contact_ref=self.recipient_contact,
            correspondent_name=self.correspondent_contact.name,
            correspondent_contact_ref=self.correspondent_contact,
            destination=self.destination,
            destination_address="26 Rue Tracking",
            destination_country="France",
            created_by=self.staff_user,
        )
        planned_event = ShipmentTrackingEvent.objects.create(
            shipment=planned_alert_shipment,
            status=ShipmentTrackingStatus.PLANNED,
            comments="planned old",
            created_by=self.staff_user,
            actor_name="Ops",
            actor_structure="ASF",
        )

        shipped_alert_shipment = Shipment.objects.create(
            status=ShipmentStatus.SHIPPED,
            shipper_name=self.shipper_contact.name,
            shipper_contact_ref=self.shipper_contact,
            recipient_name=self.recipient_contact.name,
            recipient_contact_ref=self.recipient_contact,
            correspondent_name=self.correspondent_contact.name,
            correspondent_contact_ref=self.correspondent_contact,
            destination=self.destination,
            destination_address="27 Rue Tracking",
            destination_country="France",
            created_by=self.staff_user,
        )
        boarding_event = ShipmentTrackingEvent.objects.create(
            shipment=shipped_alert_shipment,
            status=ShipmentTrackingStatus.BOARDING_OK,
            comments="boarding old",
            created_by=self.staff_user,
            actor_name="Ops",
            actor_structure="ASF",
        )

        correspondent_alert_shipment = Shipment.objects.create(
            status=ShipmentStatus.RECEIVED_CORRESPONDENT,
            shipper_name=self.shipper_contact.name,
            shipper_contact_ref=self.shipper_contact,
            recipient_name=self.recipient_contact.name,
            recipient_contact_ref=self.recipient_contact,
            correspondent_name=self.correspondent_contact.name,
            correspondent_contact_ref=self.correspondent_contact,
            destination=self.destination,
            destination_address="28 Rue Tracking",
            destination_country="France",
            created_by=self.staff_user,
        )
        received_correspondent_event = ShipmentTrackingEvent.objects.create(
            shipment=correspondent_alert_shipment,
            status=ShipmentTrackingStatus.RECEIVED_CORRESPONDENT,
            comments="received old",
            created_by=self.staff_user,
            actor_name="Ops",
            actor_structure="ASF",
        )

        closable_shipment = Shipment.objects.create(
            status=ShipmentStatus.DELIVERED,
            shipper_name=self.shipper_contact.name,
            shipper_contact_ref=self.shipper_contact,
            recipient_name=self.recipient_contact.name,
            recipient_contact_ref=self.recipient_contact,
            correspondent_name=self.correspondent_contact.name,
            correspondent_contact_ref=self.correspondent_contact,
            destination=self.destination,
            destination_address="29 Rue Tracking",
            destination_country="France",
            created_by=self.staff_user,
        )
        ShipmentTrackingEvent.objects.create(
            shipment=closable_shipment,
            status=ShipmentTrackingStatus.PLANNED,
            comments="planned",
            created_by=self.staff_user,
            actor_name="Ops",
            actor_structure="ASF",
        )
        ShipmentTrackingEvent.objects.create(
            shipment=closable_shipment,
            status=ShipmentTrackingStatus.BOARDING_OK,
            comments="boarding",
            created_by=self.staff_user,
            actor_name="Ops",
            actor_structure="ASF",
        )
        ShipmentTrackingEvent.objects.create(
            shipment=closable_shipment,
            status=ShipmentTrackingStatus.RECEIVED_CORRESPONDENT,
            comments="received",
            created_by=self.staff_user,
            actor_name="Ops",
            actor_structure="ASF",
        )
        ShipmentTrackingEvent.objects.create(
            shipment=closable_shipment,
            status=ShipmentTrackingStatus.RECEIVED_RECIPIENT,
            comments="delivered",
            created_by=self.staff_user,
            actor_name="Ops",
            actor_structure="ASF",
        )

        old_timestamp = timezone.now() - timedelta(hours=120)
        ShipmentTrackingEvent.objects.filter(
            pk__in=[
                planned_event.pk,
                boarding_event.pk,
                received_correspondent_event.pk,
            ]
        ).update(created_at=old_timestamp)

        response = self.staff_client.get("/api/v1/ui/dashboard/")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("tracking_alert_hours", payload)
        self.assertIn("tracking_cards", payload)
        self.assertGreater(payload["tracking_alert_hours"], 0)
        cards = {card["label"]: card for card in payload["tracking_cards"]}
        self.assertEqual(
            cards[f"Planifiees sans mise a bord >{payload['tracking_alert_hours']}h"]["value"],
            1,
        )
        self.assertEqual(
            cards[f"Expediees sans recu escale >{payload['tracking_alert_hours']}h"]["value"],
            1,
        )
        self.assertEqual(
            cards[f"Recu escale sans livraison >{payload['tracking_alert_hours']}h"]["value"],
            1,
        )
        self.assertEqual(cards["Dossiers cloturables"]["value"], 1)
        self.assertEqual(
            cards[f"Planifiees sans mise a bord >{payload['tracking_alert_hours']}h"]["tone"],
            "danger",
        )
        self.assertEqual(cards["Dossiers cloturables"]["tone"], "success")

    def test_ui_dashboard_exposes_technical_cards(self):
        IntegrationEvent.objects.create(
            direction=IntegrationDirection.OUTBOUND,
            source="wms.email",
            event_type="send_email",
            status=IntegrationStatus.PENDING,
        )
        fresh_processing = IntegrationEvent.objects.create(
            direction=IntegrationDirection.OUTBOUND,
            source="wms.email",
            event_type="send_email",
            status=IntegrationStatus.PROCESSING,
            processed_at=timezone.now(),
        )
        stale_processing = IntegrationEvent.objects.create(
            direction=IntegrationDirection.OUTBOUND,
            source="wms.email",
            event_type="send_email",
            status=IntegrationStatus.PROCESSING,
            processed_at=timezone.now() - timedelta(hours=24),
        )
        IntegrationEvent.objects.create(
            direction=IntegrationDirection.OUTBOUND,
            source="wms.email",
            event_type="send_email",
            status=IntegrationStatus.FAILED,
            error_message="SMTP down",
        )
        IntegrationEvent.objects.create(
            direction=IntegrationDirection.INBOUND,
            source="wms.email",
            event_type="send_email",
            status=IntegrationStatus.FAILED,
        )
        IntegrationEvent.objects.create(
            direction=IntegrationDirection.OUTBOUND,
            source="wms.sms",
            event_type="send_sms",
            status=IntegrationStatus.FAILED,
        )
        IntegrationEvent.objects.filter(pk__in=[fresh_processing.pk, stale_processing.pk]).update(
            status=IntegrationStatus.PROCESSING
        )

        response = self.staff_client.get("/api/v1/ui/dashboard/")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("queue_processing_timeout_seconds", payload)
        self.assertIn("technical_cards", payload)
        self.assertGreater(payload["queue_processing_timeout_seconds"], 0)
        cards = {card["label"]: card for card in payload["technical_cards"]}
        self.assertEqual(cards["Queue email en attente"]["value"], 1)
        self.assertEqual(cards["Queue email en traitement"]["value"], 2)
        self.assertEqual(cards["Queue email en echec"]["value"], 1)
        self.assertEqual(cards["Queue email bloquee (timeout)"]["value"], 1)
        self.assertEqual(cards["Queue email en attente"]["tone"], "warn")
        self.assertEqual(cards["Queue email en echec"]["tone"], "danger")
        self.assertEqual(cards["Queue email bloquee (timeout)"]["tone"], "danger")

    def test_ui_dashboard_exposes_pending_actions_with_age_owner_priority_and_url(self):
        disputed = Shipment.objects.create(
            status=ShipmentStatus.SHIPPED,
            shipper_name=self.shipper_contact.name,
            shipper_contact_ref=self.shipper_contact,
            recipient_name=self.recipient_contact.name,
            recipient_contact_ref=self.recipient_contact,
            correspondent_name=self.correspondent_contact.name,
            correspondent_contact_ref=self.correspondent_contact,
            destination=self.destination,
            destination_address="44 Rue Action",
            destination_country="France",
            created_by=self.staff_user,
            is_disputed=True,
        )
        Shipment.objects.filter(pk=disputed.pk).update(
            created_at=timezone.now() - timedelta(hours=12)
        )

        response = self.staff_client.get("/api/v1/ui/dashboard/")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("pending_actions", payload)
        self.assertGreaterEqual(len(payload["pending_actions"]), 1)

        for item in payload["pending_actions"]:
            self.assertIn("type", item)
            self.assertIn("reference", item)
            self.assertIn("label", item)
            self.assertIn("priority", item)
            self.assertIn("owner", item)
            self.assertIn("url", item)
            self.assertIn("age_hours", item)

        dispute_item = next(
            item for item in payload["pending_actions"] if item["reference"] == disputed.reference
        )
        self.assertEqual(dispute_item["type"], "shipment_dispute")
        self.assertEqual(dispute_item["priority"], "high")
        self.assertEqual(dispute_item["owner"], "qualite")
        self.assertGreaterEqual(dispute_item["age_hours"], 12)
        self.assertTrue(dispute_item["url"])

    def test_ui_dashboard_uses_public_query_payload_only(self):
        full_payload = build_scan_dashboard_payload(user=self.staff_user, params={})
        public_payload = {
            key: value
            for key, value in full_payload.items()
            if key not in self.DASHBOARD_QUERY_ONLY_KEYS
        }
        public_payload["kpis"] = {
            "open_shipments": 7,
            "stock_alerts": 2,
            "open_disputes": 1,
            "pending_orders": 3,
            "shipments_delayed": 4,
        }
        public_payload["timeline"] = [
            {
                "id": 1,
                "shipment_id": 99,
                "reference": "EXP-99",
                "status": "Planifié",
                "timestamp": timezone.now().isoformat(),
                "comments": "",
            }
        ]

        with mock.patch(
            "api.v1.ui_views.build_scan_dashboard_payload",
            return_value=public_payload,
        ) as mocked_builder:
            response = self.staff_client.get("/api/v1/ui/dashboard/")

        self.assertEqual(response.status_code, 200)
        mocked_builder.assert_called_once()
        payload = response.json()
        self.assertEqual(payload["kpis"], public_payload["kpis"])
        self.assertEqual(payload["timeline"], public_payload["timeline"])

    def test_ui_dashboard_exposes_document_scan_cards_alongside_email_cards(self):
        IntegrationEvent.objects.create(
            direction=IntegrationDirection.OUTBOUND,
            source="wms.document_scan",
            event_type="scan_document",
            status=IntegrationStatus.PENDING,
        )
        fresh_processing = IntegrationEvent.objects.create(
            direction=IntegrationDirection.OUTBOUND,
            source="wms.document_scan",
            event_type="scan_document",
            status=IntegrationStatus.PROCESSING,
            processed_at=timezone.now(),
        )
        stale_processing = IntegrationEvent.objects.create(
            direction=IntegrationDirection.OUTBOUND,
            source="wms.document_scan",
            event_type="scan_document",
            status=IntegrationStatus.PROCESSING,
            processed_at=timezone.now() - timedelta(hours=24),
        )
        IntegrationEvent.objects.create(
            direction=IntegrationDirection.OUTBOUND,
            source="wms.document_scan",
            event_type="scan_document",
            status=IntegrationStatus.FAILED,
            error_message="ClamAV down",
        )
        IntegrationEvent.objects.filter(pk__in=[fresh_processing.pk, stale_processing.pk]).update(
            status=IntegrationStatus.PROCESSING
        )

        response = self.staff_client.get("/api/v1/ui/dashboard/")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("document_scan_cards", payload)

        cards = {card["label"]: card for card in payload["document_scan_cards"]}
        self.assertEqual(cards["Queue scan doc en attente"]["value"], 1)
        self.assertEqual(cards["Queue scan doc en traitement"]["value"], 2)
        self.assertEqual(cards["Queue scan doc en echec"]["value"], 1)
        self.assertEqual(cards["Queue scan doc bloquee (timeout)"]["value"], 1)
        self.assertEqual(cards["Queue scan doc en attente"]["tone"], "warn")
        self.assertEqual(cards["Queue scan doc en echec"]["tone"], "danger")
        self.assertEqual(cards["Queue scan doc bloquee (timeout)"]["tone"], "danger")

    def test_ui_dashboard_pending_actions_use_stable_owner_and_priority_vocab(self):
        Shipment.objects.create(
            status=ShipmentStatus.SHIPPED,
            shipper_name=self.shipper_contact.name,
            shipper_contact_ref=self.shipper_contact,
            recipient_name=self.recipient_contact.name,
            recipient_contact_ref=self.recipient_contact,
            correspondent_name=self.correspondent_contact.name,
            correspondent_contact_ref=self.correspondent_contact,
            destination=self.destination,
            destination_address="45 Rue Action",
            destination_country="France",
            created_by=self.staff_user,
            is_disputed=True,
        )

        response = self.staff_client.get("/api/v1/ui/dashboard/")
        self.assertEqual(response.status_code, 200)
        payload = response.json()

        allowed_owners = {"magasin", "qualite", "admin", "portal"}
        allowed_priorities = {"high", "medium", "low"}
        self.assertGreaterEqual(len(payload["pending_actions"]), 1)
        for item in payload["pending_actions"]:
            self.assertIn(item["owner"], allowed_owners)
            self.assertIn(item["priority"], allowed_priorities)

    def test_ui_dashboard_exposes_sla_alert_summary_cards_and_rows(self):
        self._create_delayed_dashboard_shipment(
            reference="API-SLA-NEW",
            shipment_status=ShipmentStatus.PLANNED,
            tracking_status=ShipmentTrackingStatus.PLANNED,
            hours_ago=80,
        )
        persistent = self._create_delayed_dashboard_shipment(
            reference="API-SLA-PERSISTENT",
            shipment_status=ShipmentStatus.SHIPPED,
            tracking_status=ShipmentTrackingStatus.BOARDING_OK,
            hours_ago=170,
        )
        critical = self._create_delayed_dashboard_shipment(
            reference="API-SLA-CRITICAL",
            shipment_status=ShipmentStatus.RECEIVED_CORRESPONDENT,
            tracking_status=ShipmentTrackingStatus.RECEIVED_CORRESPONDENT,
            hours_ago=250,
        )

        response = self.staff_client.get("/api/v1/ui/dashboard/")
        self.assertEqual(response.status_code, 200)
        payload = response.json()

        self.assertIn("sla_alert_summary_cards", payload)
        self.assertIn("sla_alert_rows", payload)

        summary_cards = {
            card["label"]: card["value"] for card in payload["sla_alert_summary_cards"]
        }
        self.assertEqual(summary_cards["Nouveaux retards"], 1)
        self.assertEqual(summary_cards["Retards persistants"], 1)
        self.assertEqual(summary_cards["Retards critiques"], 1)

        rows_by_reference = {row["reference"]: row for row in payload["sla_alert_rows"]}
        self.assertEqual(
            rows_by_reference["API-SLA-PERSISTENT"]["segment"], "OK mise a bord -> Recu escale"
        )
        self.assertEqual(rows_by_reference["API-SLA-PERSISTENT"]["owner"], "qualite")
        self.assertEqual(rows_by_reference["API-SLA-PERSISTENT"]["freshness"], "persistent")
        self.assertEqual(rows_by_reference["API-SLA-PERSISTENT"]["severity"], "high")
        self.assertGreater(rows_by_reference["API-SLA-PERSISTENT"]["delay_hours"], 95)

        self.assertEqual(
            rows_by_reference["API-SLA-CRITICAL"]["segment"],
            "Recu escale -> Livre",
        )
        self.assertEqual(rows_by_reference["API-SLA-CRITICAL"]["owner"], "portal")
        self.assertEqual(rows_by_reference["API-SLA-CRITICAL"]["freshness"], "persistent")
        self.assertEqual(rows_by_reference["API-SLA-CRITICAL"]["severity"], "critical")
        self.assertGreater(rows_by_reference["API-SLA-CRITICAL"]["delay_hours"], 175)
        self.assertEqual(
            rows_by_reference["API-SLA-CRITICAL"]["url"],
            reverse("scan:scan_shipment_track", args=[critical.tracking_token]),
        )
        self.assertEqual(payload["sla_alert_rows"][0]["reference"], critical.reference)

    def test_ui_dashboard_exposes_stock_cards(self):
        ProductLot.objects.create(
            product=self.product,
            lot_code="LOT-EXTRA",
            status=ProductLotStatus.AVAILABLE,
            quantity_on_hand=5,
            quantity_reserved=2,
            location=self.product_lot.location,
        )

        response = self.staff_client.get("/api/v1/ui/dashboard/")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("stock_cards", payload)
        cards = {card["label"]: card for card in payload["stock_cards"]}

        available_lots = ProductLot.objects.filter(
            status=ProductLotStatus.AVAILABLE,
            quantity_on_hand__gt=0,
        )
        total_available_qty = sum(
            lot.quantity_on_hand - lot.quantity_reserved for lot in available_lots
        )
        self.assertEqual(
            cards["Produits actifs"]["value"],
            Product.objects.filter(is_active=True).count(),
        )
        self.assertEqual(cards["Lots disponibles"]["value"], available_lots.count())
        self.assertEqual(cards["Quantite disponible"]["value"], total_available_qty)

        threshold = payload["low_stock_threshold"]
        low_stock_label = f"Stock bas (< {threshold})"
        self.assertIn(low_stock_label, cards)
        self.assertEqual(cards[low_stock_label]["value"], len(payload["low_stock_rows"]))
        self.assertEqual(cards[low_stock_label]["tone"], "danger")

    def test_ui_dashboard_exposes_workflow_blockage_and_sla_cards(self):
        stale_draft = Shipment.objects.create(
            status=ShipmentStatus.DRAFT,
            reference=f"{TEMP_SHIPMENT_REFERENCE_PREFIX}42",
            shipper_name=self.shipper_contact.name,
            shipper_contact_ref=self.shipper_contact,
            recipient_name=self.recipient_contact.name,
            recipient_contact_ref=self.recipient_contact,
            correspondent_name=self.correspondent_contact.name,
            correspondent_contact_ref=self.correspondent_contact,
            destination=self.destination,
            destination_address="40 Rue Workflow",
            destination_country="France",
            created_by=self.staff_user,
        )
        Shipment.objects.filter(pk=stale_draft.pk).update(
            created_at=timezone.now() - timedelta(hours=120)
        )

        approved_order = Order.objects.create(
            review_status=OrderReviewStatus.APPROVED,
            shipper_name=self.shipper_contact.name,
            recipient_name=self.recipient_contact.name,
            correspondent_name=self.correspondent_contact.name,
            destination_address="41 Rue Workflow",
            destination_country="France",
            created_by=self.staff_user,
        )
        Order.objects.filter(pk=approved_order.pk).update(
            created_at=timezone.now() - timedelta(hours=120)
        )

        Shipment.objects.create(
            status=ShipmentStatus.SHIPPED,
            shipper_name=self.shipper_contact.name,
            shipper_contact_ref=self.shipper_contact,
            recipient_name=self.recipient_contact.name,
            recipient_contact_ref=self.recipient_contact,
            correspondent_name=self.correspondent_contact.name,
            correspondent_contact_ref=self.correspondent_contact,
            destination=self.destination,
            destination_address="42 Rue Workflow",
            destination_country="France",
            created_by=self.staff_user,
            is_disputed=True,
        )

        delivered = Shipment.objects.create(
            status=ShipmentStatus.DELIVERED,
            shipper_name=self.shipper_contact.name,
            shipper_contact_ref=self.shipper_contact,
            recipient_name=self.recipient_contact.name,
            recipient_contact_ref=self.recipient_contact,
            correspondent_name=self.correspondent_contact.name,
            correspondent_contact_ref=self.correspondent_contact,
            destination=self.destination,
            destination_address="43 Rue SLA",
            destination_country="France",
            created_by=self.staff_user,
        )
        planned = ShipmentTrackingEvent.objects.create(
            shipment=delivered,
            status=ShipmentTrackingStatus.PLANNED,
            comments="planned",
            created_by=self.staff_user,
            actor_name="Ops",
            actor_structure="ASF",
        )
        boarding = ShipmentTrackingEvent.objects.create(
            shipment=delivered,
            status=ShipmentTrackingStatus.BOARDING_OK,
            comments="boarding",
            created_by=self.staff_user,
            actor_name="Ops",
            actor_structure="ASF",
        )
        received_correspondent = ShipmentTrackingEvent.objects.create(
            shipment=delivered,
            status=ShipmentTrackingStatus.RECEIVED_CORRESPONDENT,
            comments="received correspondent",
            created_by=self.staff_user,
            actor_name="Ops",
            actor_structure="ASF",
        )
        received_recipient = ShipmentTrackingEvent.objects.create(
            shipment=delivered,
            status=ShipmentTrackingStatus.RECEIVED_RECIPIENT,
            comments="received recipient",
            created_by=self.staff_user,
            actor_name="Ops",
            actor_structure="ASF",
        )
        now = timezone.now()
        ShipmentTrackingEvent.objects.filter(pk=planned.pk).update(
            created_at=now - timedelta(hours=400)
        )
        ShipmentTrackingEvent.objects.filter(pk=boarding.pk).update(
            created_at=now - timedelta(hours=300)
        )
        ShipmentTrackingEvent.objects.filter(pk=received_correspondent.pk).update(
            created_at=now - timedelta(hours=200)
        )
        ShipmentTrackingEvent.objects.filter(pk=received_recipient.pk).update(
            created_at=now - timedelta(hours=100)
        )

        response = self.staff_client.get("/api/v1/ui/dashboard/")
        self.assertEqual(response.status_code, 200)
        payload = response.json()

        self.assertIn("workflow_blockage_hours", payload)
        self.assertIn("workflow_blockage_cards", payload)
        self.assertIn("sla_cards", payload)
        self.assertGreater(payload["workflow_blockage_hours"], 0)
        self.assertGreater(payload["tracking_alert_hours"], 0)

        workflow_cards = {card["label"]: card for card in payload["workflow_blockage_cards"]}
        workflow_hours = payload["workflow_blockage_hours"]
        self.assertEqual(
            workflow_cards[f"Expeditions Creation/En cours >{workflow_hours}h"]["value"],
            1,
        )
        self.assertEqual(
            workflow_cards[f"Cmd validees sans expedition >{workflow_hours}h"]["value"],
            1,
        )
        self.assertEqual(workflow_cards["Dossiers livres non clos"]["value"], 1)
        self.assertEqual(workflow_cards["Dossiers en litige ouverts"]["value"], 1)
        self.assertEqual(
            workflow_cards[f"Expeditions Creation/En cours >{workflow_hours}h"]["tone"],
            "danger",
        )
        self.assertEqual(
            workflow_cards[f"Cmd validees sans expedition >{workflow_hours}h"]["tone"],
            "danger",
        )
        self.assertEqual(workflow_cards["Dossiers livres non clos"]["tone"], "warn")
        self.assertEqual(workflow_cards["Dossiers en litige ouverts"]["tone"], "danger")

        tracking_alert_hours = payload["tracking_alert_hours"]
        sla_cards = {card["label"]: card for card in payload["sla_cards"]}
        self.assertEqual(
            sla_cards[f"Planifie -> OK mise a bord >{tracking_alert_hours}h"]["value"],
            "1 / 1",
        )
        self.assertEqual(
            sla_cards[f"OK mise a bord -> Recu escale >{tracking_alert_hours}h"]["value"],
            "1 / 1",
        )
        self.assertEqual(
            sla_cards[f"Recu escale -> Livre >{tracking_alert_hours}h"]["value"],
            "1 / 1",
        )
        self.assertEqual(
            sla_cards[f"Planifie -> Livre >{tracking_alert_hours * 3}h"]["value"],
            "1 / 1",
        )
        self.assertEqual(
            sla_cards[f"Planifie -> OK mise a bord >{tracking_alert_hours}h"]["tone"],
            "danger",
        )

    def test_ui_dashboard_exposes_destination_risk_rows(self):
        secondary_destination = Destination.objects.create(
            city="BZV",
            iata_code="BZV-UI",
            country="Congo",
            correspondent_contact=self.correspondent_contact,
            is_active=True,
        )
        self._create_workflow_projection(
            reference="EXP-UI-RISK-RUN-1",
            destination=self.destination,
            delay_state="persistent",
            has_open_dispute=True,
            active_blockage_category="creation_expedition",
            segment_age_hours=72,
        )
        self._create_workflow_projection(
            reference="EXP-UI-RISK-BZV-1",
            destination=secondary_destination,
            delay_state="critical",
            has_open_dispute=True,
            active_blockage_category="suivi",
            segment_age_hours=144,
        )

        response = self.staff_client.get("/api/v1/ui/dashboard/")
        self.assertEqual(response.status_code, 200)
        payload = response.json()

        self.assertIn("destination_risk_summary_cards", payload)
        self.assertIn("destination_risk_rows", payload)
        summary_cards = {
            card["label"]: card["value"] for card in payload["destination_risk_summary_cards"]
        }
        self.assertEqual(summary_cards["Destinations critiques"], 1)
        self.assertEqual(summary_cards["Destinations avec litiges"], 2)
        self.assertEqual(summary_cards["Plus ancien dossier ouvert"], "144.0h")

        rows = payload["destination_risk_rows"]
        self.assertEqual(rows[0]["destination_id"], secondary_destination.id)
        self.assertEqual(rows[0]["destination_label"], str(secondary_destination))
        self.assertEqual(rows[0]["delayed_shipment_count"], 1)
        self.assertEqual(rows[0]["critical_shipment_count"], 1)
        self.assertEqual(rows[0]["open_dispute_count"], 1)
        self.assertEqual(rows[0]["top_blockage_category"], "Suivi")
        self.assertEqual(rows[0]["oldest_open_segment_age_hours"], 144)
        self.assertEqual(
            rows[0]["url"],
            f"{reverse('scan:scan_shipments_tracking')}?destination={secondary_destination.id}",
        )
        self.assertEqual(rows[0]["cta_label"], "Ouvrir les dossiers")

    def test_ui_dashboard_exposes_destination_risk_week_trend(self):
        secondary_destination = Destination.objects.create(
            city="BZV",
            iata_code="BZV-UI-TREND",
            country="Congo",
            correspondent_contact=self.correspondent_contact,
            is_active=True,
        )
        current_week_planned_at = timezone.make_aware(datetime(2026, 3, 31, 10, 0))
        previous_week_planned_at = timezone.make_aware(datetime(2026, 3, 24, 10, 0))
        self._create_workflow_projection(
            reference="EXP-UI-RISK-TREND-1",
            destination=self.destination,
            delay_state="persistent",
            has_open_dispute=True,
            active_blockage_category="suivi",
            segment_age_hours=72,
            planned_at=current_week_planned_at,
        )
        self._create_workflow_projection(
            reference="EXP-UI-RISK-TREND-2",
            destination=self.destination,
            delay_state="new",
            has_open_dispute=False,
            active_blockage_category="creation_expedition",
            segment_age_hours=48,
            planned_at=previous_week_planned_at,
        )
        self._create_workflow_projection(
            reference="EXP-UI-RISK-TREND-3",
            destination=secondary_destination,
            delay_state="critical",
            has_open_dispute=True,
            active_blockage_category="suivi",
            segment_age_hours=144,
            planned_at=current_week_planned_at,
        )

        with mock.patch(
            "django.utils.timezone.localdate",
            return_value=date(2026, 3, 31),
        ):
            response = self.staff_client.get("/api/v1/ui/dashboard/")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        rows_by_destination = {
            row["destination_id"]: row for row in payload["destination_risk_rows"]
        }
        trend_row = rows_by_destination[self.destination.id]
        self.assertEqual(trend_row["current_week_label"], "2026-W14")
        self.assertEqual(trend_row["current_week_score"], 2)
        self.assertEqual(trend_row["previous_week_label"], "2026-W13")
        self.assertEqual(trend_row["previous_week_score"], 1)
        self.assertEqual(trend_row["trend_delta"], 1)
        self.assertEqual(trend_row["trend_direction"], "up")
        self.assertEqual(trend_row["trend_label"], "+1")

        missing_previous_row = rows_by_destination[secondary_destination.id]
        self.assertEqual(missing_previous_row["current_week_score"], 3)
        self.assertEqual(missing_previous_row["previous_week_score"], 0)

    def test_ui_dashboard_exposes_workflow_blockage_rows_and_claim_state(self):
        stale_draft = Shipment.objects.create(
            status=ShipmentStatus.DRAFT,
            reference=f"{TEMP_SHIPMENT_REFERENCE_PREFIX}84",
            shipper_name=self.shipper_contact.name,
            shipper_contact_ref=self.shipper_contact,
            recipient_name=self.recipient_contact.name,
            recipient_contact_ref=self.recipient_contact,
            correspondent_name=self.correspondent_contact.name,
            correspondent_contact_ref=self.correspondent_contact,
            destination=self.destination,
            destination_address="44 Rue Workflow",
            destination_country="France",
            created_by=self.staff_user,
        )
        Shipment.objects.filter(pk=stale_draft.pk).update(
            created_at=timezone.now() - timedelta(hours=120)
        )

        approved_order = Order.objects.create(
            review_status=OrderReviewStatus.APPROVED,
            shipper_name=self.shipper_contact.name,
            recipient_name=self.recipient_contact.name,
            correspondent_name=self.correspondent_contact.name,
            destination_address="45 Rue Workflow",
            destination_country="France",
            created_by=self.staff_user,
        )
        Order.objects.filter(pk=approved_order.pk).update(
            created_at=timezone.now() - timedelta(hours=120)
        )

        dispute = Shipment.objects.create(
            status=ShipmentStatus.PLANNED,
            reference="EXP-API-DISPUTE",
            shipper_name=self.shipper_contact.name,
            shipper_contact_ref=self.shipper_contact,
            recipient_name=self.recipient_contact.name,
            recipient_contact_ref=self.recipient_contact,
            correspondent_name=self.correspondent_contact.name,
            correspondent_contact_ref=self.correspondent_contact,
            destination=self.destination,
            destination_address="46 Rue Workflow",
            destination_country="France",
            created_by=self.staff_user,
            is_disputed=True,
        )
        Shipment.objects.filter(pk=dispute.pk).update(
            disputed_at=timezone.now() - timedelta(hours=96)
        )

        delivered = Shipment.objects.create(
            status=ShipmentStatus.DELIVERED,
            reference="EXP-API-CLOSE",
            shipper_name=self.shipper_contact.name,
            shipper_contact_ref=self.shipper_contact,
            recipient_name=self.recipient_contact.name,
            recipient_contact_ref=self.recipient_contact,
            correspondent_name=self.correspondent_contact.name,
            correspondent_contact_ref=self.correspondent_contact,
            destination=self.destination,
            destination_address="47 Rue Workflow",
            destination_country="France",
            created_by=self.staff_user,
        )
        delivered_event = ShipmentTrackingEvent.objects.create(
            shipment=delivered,
            status=ShipmentTrackingStatus.RECEIVED_RECIPIENT,
            comments="delivered",
            created_by=self.staff_user,
            actor_name="Ops",
            actor_structure="ASF",
        )
        ShipmentTrackingEvent.objects.filter(pk=delivered_event.pk).update(
            created_at=timezone.now() - timedelta(hours=48)
        )

        email_processing = IntegrationEvent.objects.create(
            direction=IntegrationDirection.OUTBOUND,
            source="wms.email",
            target="smtp",
            event_type="send_email",
            payload={"subject": "Processing"},
            status=IntegrationStatus.PROCESSING,
        )
        IntegrationEvent.objects.filter(pk=email_processing.pk).update(
            processed_at=timezone.now() - timedelta(minutes=30)
        )

        IntegrationEvent.objects.create(
            direction=IntegrationDirection.OUTBOUND,
            source="wms.document_scan",
            target="antivirus",
            event_type="scan_document",
            payload={"document_id": 99},
            status=IntegrationStatus.FAILED,
            error_message="ClamAV error",
        )

        claimed_key = f"commande:order:{approved_order.pk}"
        WorkflowBlockageClaim.objects.create(
            blockage_key=claimed_key,
            category="commande",
            label="Creer expedition",
            reference=approved_order.reference or f"CMD-{approved_order.pk}",
            owner="admin",
            claimed_by=self.staff_user,
        )

        response = self.staff_client.get("/api/v1/ui/dashboard/")
        self.assertEqual(response.status_code, 200)
        payload = response.json()

        self.assertIn("workflow_blockage_rows", payload)
        self.assertIn("workflow_blockage_summary_cards", payload)
        rows = payload["workflow_blockage_rows"]
        self.assertEqual(
            {row["category"] for row in rows},
            {
                "creation_expedition",
                "commande",
                "suivi",
                "cloture",
                "queue",
            },
        )
        claimed_row = next(row for row in rows if row["blockage_key"] == claimed_key)
        self.assertTrue(claimed_row["is_claimed"])
        self.assertEqual(claimed_row["claimed_by"], self.staff_user.get_username())
        self.assertTrue(
            any(
                row["category"] == "queue" and row["reference"] == "wms.document_scan"
                for row in rows
            )
        )
        self.assertTrue(any(row["category"] == "cloture" for row in rows))

    def test_ui_dashboard_workflow_blockage_claim_endpoint(self):
        stale_draft = Shipment.objects.create(
            status=ShipmentStatus.DRAFT,
            reference=f"{TEMP_SHIPMENT_REFERENCE_PREFIX}99",
            shipper_name=self.shipper_contact.name,
            shipper_contact_ref=self.shipper_contact,
            recipient_name=self.recipient_contact.name,
            recipient_contact_ref=self.recipient_contact,
            correspondent_name=self.correspondent_contact.name,
            correspondent_contact_ref=self.correspondent_contact,
            destination=self.destination,
            destination_address="48 Rue Workflow",
            destination_country="France",
            created_by=self.staff_user,
        )
        Shipment.objects.filter(pk=stale_draft.pk).update(
            created_at=timezone.now() - timedelta(hours=120)
        )

        dashboard_response = self.staff_client.get("/api/v1/ui/dashboard/")
        self.assertEqual(dashboard_response.status_code, 200)
        blockage_row = next(
            row
            for row in dashboard_response.json()["workflow_blockage_rows"]
            if row["reference"] == stale_draft.reference
        )

        claim_response = self.staff_client.post(
            "/api/v1/ui/dashboard/workflow-blockages/claims/",
            {"action": "claim", "blockage_key": blockage_row["blockage_key"]},
            format="json",
        )
        self.assertEqual(claim_response.status_code, 200)
        self.assertEqual(claim_response.json()["claim_state"], "claimed")
        self.assertTrue(
            WorkflowBlockageClaim.objects.filter(
                blockage_key=blockage_row["blockage_key"],
                claimed_by=self.staff_user,
            ).exists()
        )

        release_response = self.staff_client.post(
            "/api/v1/ui/dashboard/workflow-blockages/claims/",
            {"action": "release", "blockage_key": blockage_row["blockage_key"]},
            format="json",
        )
        self.assertEqual(release_response.status_code, 200)
        self.assertEqual(release_response.json()["claim_state"], "released")
        self.assertFalse(
            WorkflowBlockageClaim.objects.filter(blockage_key=blockage_row["blockage_key"]).exists()
        )

    def test_ui_pilotage_exposes_summary_escalations_and_export_health(self):
        snapshot_date = timezone.localdate()
        OpsPilotageSnapshot.objects.create(
            snapshot_date=snapshot_date,
            scope_type="global",
            scope_key="all",
            metric_key="sla_critical_count",
            metric_value=3,
            payload={},
        )
        OpsPilotageSnapshot.objects.create(
            snapshot_date=snapshot_date,
            scope_type="planning_export",
            scope_key="27",
            metric_key="planning_pdf_ok",
            metric_value=0,
            payload={"version_id": 27, "run_id": 9},
        )
        OpsPilotageSnapshot.objects.create(
            snapshot_date=snapshot_date,
            scope_type="planning_export",
            scope_key="27",
            metric_key="planning_workbook_ok",
            metric_value=1,
            payload={"version_id": 27, "run_id": 9},
        )
        OpsEscalation.objects.create(
            escalation_key="planning_pdf_missing:version:27",
            category="planning_pdf_missing",
            scope_type="planning_version",
            scope_key="27",
            severity="high",
            owner="admin",
            status="open",
            payload={"version_id": 27, "run_id": 9},
        )
        self._create_workflow_projection(
            reference="EXP-PILOTAGE-API-001",
            destination=self.destination,
            delay_state="critical",
            has_open_dispute=True,
            active_blockage_category="suivi",
            segment_age_hours=132.0,
        )

        response = self.staff_client.get("/api/v1/ui/pilotage/")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("summary_cards", payload)
        self.assertIn("priority_rows", payload)
        self.assertIn("escalation_rows", payload)
        self.assertIn("destination_trend_rows", payload)
        self.assertIn("planning_export_rows", payload)
        self.assertIn("portal_backlog_rows", payload)
        self.assertEqual(payload["escalation_rows"][0]["category"], "planning_pdf_missing")
        self.assertFalse(payload["planning_export_rows"][0]["pdf_ok"])

    def test_ui_stock_returns_products_and_filters(self):
        response = self.staff_client.get("/api/v1/ui/stock/?q=UI%20API")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["filters"]["q"], "UI API")
        self.assertFalse(payload["filters"]["include_zero"])
        self.assertEqual(payload["meta"]["total_products"], 1)
        self.assertEqual(payload["products"][0]["sku"], self.product.sku)

    def test_ui_stock_include_zero_returns_out_of_stock_products(self):
        Product.objects.create(
            sku="UI-API-ZERO-001",
            name="UI API Zero Product",
            brand="Medi",
            default_location=self.product.default_location,
            is_active=True,
            qr_code_image="qr_codes/test.png",
        )

        response_default = self.staff_client.get("/api/v1/ui/stock/?q=UI-API-ZERO-001")
        self.assertEqual(response_default.status_code, 200)
        payload_default = response_default.json()
        self.assertFalse(payload_default["filters"]["include_zero"])
        self.assertEqual(payload_default["meta"]["total_products"], 0)

        response = self.staff_client.get("/api/v1/ui/stock/?q=UI-API-ZERO-001&include_zero=1")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["filters"]["include_zero"])
        self.assertEqual(payload["meta"]["total_products"], 1)
        self.assertEqual(payload["products"][0]["sku"], "UI-API-ZERO-001")
        self.assertEqual(payload["products"][0]["stock_total"], 0)

    def test_ui_stock_exposes_brand_and_barcode_fields(self):
        product = Product.objects.create(
            sku="UI-API-BAR-001",
            name="UI API Barcode Product",
            brand="Brand Barcode",
            barcode="BARCODE-UI-001",
            default_location=self.product.default_location,
            is_active=True,
            qr_code_image="qr_codes/test.png",
        )
        ProductLot.objects.create(
            product=product,
            lot_code="LOT-BARCODE",
            status=ProductLotStatus.AVAILABLE,
            quantity_on_hand=3,
            quantity_reserved=0,
            location=self.product_lot.location,
        )

        response = self.staff_client.get("/api/v1/ui/stock/?q=UI-API-BAR-001")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["meta"]["total_products"], 1)
        row = payload["products"][0]
        product.refresh_from_db()
        self.assertEqual(row["sku"], "UI-API-BAR-001")
        self.assertEqual(row["brand"], product.brand)
        self.assertEqual(row["barcode"], "BARCODE-UI-001")

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
        destination_row = next(
            (item for item in payload["destinations"] if item.get("id") == self.destination.id),
            None,
        )
        self.assertIsNotNone(destination_row)
        self.assertEqual(destination_row["label"], str(self.destination))

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

    def test_ui_button_document_urls_keep_legacy_mapping_and_return_pdf(self):
        shipment_carton = Carton.objects.create(
            code="UI-BTN-CARTON",
            status=CartonStatus.ASSIGNED,
            shipment=self.shipment,
        )
        CartonItem.objects.create(
            carton=shipment_carton,
            product_lot=self.product_lot,
            quantity=1,
        )
        artifact = GeneratedPrintArtifact.objects.create(
            pack_code="B",
            status=GeneratedPrintArtifactStatus.SYNC_PENDING,
        )
        artifact.pdf_file.save("button-mapping.pdf", ContentFile(b"%PDF-button"), save=True)
        web_client = Client()
        web_client.force_login(self.staff_user)

        with (
            mock.patch(
                "wms.views_print_docs.generate_pack",
                return_value=artifact,
            ),
            mock.patch(
                "wms.views_print_labels.generate_pack",
                return_value=artifact,
            ),
        ):
            ready_response = self.staff_client.get("/api/v1/ui/shipments/ready/")
            self.assertEqual(ready_response.status_code, 200)
            shipment_row = next(
                row for row in ready_response.json()["shipments"] if row["id"] == self.shipment.id
            )
            documents = shipment_row["documents"]
            self.assertTrue(documents["shipment_note_url"].endswith("/doc/shipment_note/"))
            self.assertTrue(
                documents["packing_list_shipment_url"].endswith("/doc/packing_list_shipment/")
            )
            self.assertTrue(
                documents["donation_certificate_url"].endswith("/doc/donation_certificate/")
            )
            self.assertTrue(documents["labels_url"].endswith("/labels/"))

            for url in (
                documents["shipment_note_url"],
                documents["packing_list_shipment_url"],
                documents["donation_certificate_url"],
                documents["labels_url"],
            ):
                pdf_response = web_client.get(url)
                self.assertEqual(pdf_response.status_code, 200)
                self.assertTrue(pdf_response["Content-Type"].startswith("application/pdf"))

            label_detail_response = self.staff_client.get(
                f"/api/v1/ui/shipments/{self.shipment.id}/labels/{shipment_carton.id}/"
            )
            self.assertEqual(label_detail_response.status_code, 200)
            label_detail_url = label_detail_response.json()["url"]
            self.assertTrue(label_detail_url.endswith(f"/labels/{shipment_carton.id}/"))
            detail_pdf_response = web_client.get(label_detail_url)
            self.assertEqual(detail_pdf_response.status_code, 200)
            self.assertTrue(detail_pdf_response["Content-Type"].startswith("application/pdf"))

            cartons_response = self.staff_client.get("/api/v1/ui/cartons/")
            self.assertEqual(cartons_response.status_code, 200)
            carton_row = next(
                row for row in cartons_response.json()["cartons"] if row["id"] == shipment_carton.id
            )
            self.assertTrue(
                carton_row["packing_list_url"].endswith(
                    f"/shipment/{self.shipment.id}/carton/{shipment_carton.id}/doc/"
                )
            )
            self.assertTrue(
                carton_row["picking_url"].endswith(f"/carton/{shipment_carton.id}/picking/")
            )
            for url in (carton_row["packing_list_url"], carton_row["picking_url"]):
                pdf_response = web_client.get(url)
                self.assertEqual(pdf_response.status_code, 200)
                self.assertTrue(pdf_response["Content-Type"].startswith("application/pdf"))

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

        tracked_row = next(row for row in payload_all["shipments"] if row["id"] == self.shipment.id)
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
        response = self.staff_client.get("/api/v1/ui/shipments/tracking/?planned_week=invalid-week")
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

    def test_ui_portal_dashboard_returns_recipient_scope_payload_for_active_grant(self):
        response = self.recipient_scope_client.get("/api/v1/ui/portal/dashboard/")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["mode"], "recipient")
        self.assertEqual(
            payload["recipient"]["recipient_organization_id"],
            self.shipment_recipient_organization.id,
        )
        self.assertEqual(
            payload["recipient"]["structure_name"],
            self.recipient_contact.name,
        )

    def test_ui_portal_dashboard_exposes_step_guidance_and_summary_counts(self):
        portal_shipment = Shipment.objects.create(
            status=ShipmentStatus.PLANNED,
            shipper_name="ASF Hub",
            shipper_contact_ref=self.shipper_contact,
            recipient_name="Recipient",
            recipient_contact_ref=self.recipient_contact,
            correspondent_name="M. Dupont",
            correspondent_contact_ref=self.correspondent_contact,
            destination=self.destination,
            destination_address="30 Rue Test",
            destination_country="France",
            created_by=self.staff_user,
        )
        changes_requested = Order.objects.create(
            association_contact=self.association_contact,
            review_status=OrderReviewStatus.CHANGES_REQUESTED,
            shipper_name="Sender",
            recipient_name="Recipient",
            correspondent_name="Correspondent",
            destination_address="21 Rue Test",
            destination_country="France",
            created_by=self.staff_user,
        )
        shipped_order = Order.objects.create(
            association_contact=self.association_contact,
            review_status=OrderReviewStatus.APPROVED,
            shipper_name="Sender",
            recipient_name="Recipient",
            correspondent_name="Correspondent",
            destination_address="22 Rue Test",
            destination_country="France",
            created_by=self.staff_user,
            shipment=portal_shipment,
        )

        response = self.portal_client.get("/api/v1/ui/portal/dashboard/")
        self.assertEqual(response.status_code, 200)
        payload = response.json()

        self.assertIn("kpis", payload)
        self.assertEqual(payload["kpis"]["orders_total"], 3)
        self.assertEqual(payload["kpis"]["orders_pending_review"], 1)
        self.assertEqual(payload["kpis"]["orders_changes_requested"], 1)
        self.assertEqual(payload["kpis"]["orders_with_shipment"], 1)

        rows = {row["id"]: row for row in payload["orders"]}
        self.assertEqual(
            rows[self.portal_order.id]["next_step_label"], "Attendre la validation ASF"
        )
        self.assertEqual(rows[self.portal_order.id]["next_step_tone"], "info")
        self.assertEqual(rows[changes_requested.id]["next_step_label"], "Corriger la commande")
        self.assertEqual(rows[shipped_order.id]["next_step_label"], "Suivre l'expédition")

    def test_ui_portal_dashboard_uses_shared_payload_without_html_orders(self):
        profile = AssociationProfile.objects.get(user=self.portal_user)
        payload = build_portal_dashboard_payload(profile=profile)
        payload.pop("orders", None)

        with mock.patch("api.v1.ui_views.build_portal_dashboard_payload", return_value=payload):
            response = self.portal_client.get("/api/v1/ui/portal/dashboard/")

        self.assertEqual(response.status_code, 200)
        response_payload = response.json()
        self.assertEqual(response_payload["kpis"], payload["dashboard_kpis"])
        self.assertEqual(response_payload["orders"], payload["order_rows"])

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
        shipment = Shipment.objects.get(pk=shipment_id)
        self.available_carton.refresh_from_db()
        self.assertEqual(self.available_carton.shipment_id, shipment_id)
        self.assertEqual(self.available_carton.status, CartonStatus.ASSIGNED)
        self.assertGreaterEqual(Carton.objects.filter(shipment_id=shipment_id).count(), 2)
        self.assertEqual(
            shipment.party_snapshot["shipper"]["contact"]["contact_id"],
            self.shipper_referent.id,
        )
        self.assertEqual(
            shipment.party_snapshot["recipient"]["contact"]["contact_id"],
            self.recipient_referent.id,
        )

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
        editable_shipment.refresh_from_db()
        self.assertEqual(
            editable_shipment.party_snapshot["shipper"]["contact"]["contact_id"],
            self.shipper_referent.id,
        )
        self.assertEqual(
            editable_shipment.party_snapshot["recipient"]["contact"]["contact_id"],
            self.recipient_referent.id,
        )

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

    def test_ui_tracking_event_accepts_manual_carton_proof_for_receipt_step(self):
        track_shipment = Shipment.objects.create(
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

        response = self.staff_client.post(
            f"/api/v1/ui/shipments/{track_shipment.id}/tracking-events/",
            {
                "status": ShipmentTrackingStatus.RECEIVED_CORRESPONDENT,
                "actor_name": "Operateur",
                "actor_structure": "ASF",
                "proof_no_photo": True,
                "proof_carton_reference": "IATA-LOCAL-001",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        tracking_event = ShipmentTrackingEvent.objects.get(shipment=track_shipment)
        self.assertEqual(tracking_event.proof_mode, ShipmentTrackingProofMode.MANUAL)
        self.assertEqual(tracking_event.proof_carton_reference, "IATA-LOCAL-001")

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
        self.assertEqual(
            created_order.association_contact_id, self.portal_order.association_contact_id
        )
        self.assertEqual(created_order.lines.count(), 1)
        self.assertIsNotNone(created_order.shipment_id)

    def test_ui_portal_order_create_uses_shared_resolution_and_submission_use_cases(self):
        fake_order = Order.objects.create(
            association_contact=self.association_contact,
            shipper_name=self.association_contact.name,
            shipper_contact=self.association_contact,
            recipient_name="Recipient Shared",
            recipient_contact=self.portal_recipient.synced_contact,
            destination_address="1 Rue Shared",
            destination_city=self.destination.city,
            destination_country=self.destination.country,
        )
        destination_payload = {
            "recipient_name": "Recipient Shared",
            "recipient_contact": self.portal_recipient.synced_contact,
            "destination_city": self.destination.city,
            "destination_country": self.destination.country,
            "destination_address": "1 Rue Shared",
        }

        with mock.patch(
            "api.v1.ui_views.resolve_portal_order_destination",
            create=True,
            return_value=(destination_payload, ""),
        ) as resolve_destination:
            with mock.patch(
                "api.v1.ui_views.submit_portal_order",
                create=True,
                return_value=fake_order,
            ) as submit_order:
                with mock.patch("api.v1.ui_views.send_portal_order_notifications"):
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
        resolve_destination.assert_called_once()
        submit_order.assert_called_once()

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

    def test_ui_portal_recipients_post_uses_shared_profile_use_case(self):
        with mock.patch(
            "api.v1.ui_views.update_recipient_shared_profile",
            create=True,
            wraps=update_recipient_shared_profile,
        ) as update_shared_profile:
            response = self.portal_client.post(
                "/api/v1/ui/portal/recipients/",
                {
                    "destination_id": self.destination.id,
                    "structure_name": "Canonical API Structure",
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

        self.assertEqual(response.status_code, 201)
        update_shared_profile.assert_called_once()

    def test_ui_portal_recipient_patch_uses_active_recipient_scope(self):
        with mock.patch(
            "api.v1.ui_views.update_runtime_recipient_profile",
            create=True,
        ) as update_runtime_profile:
            update_runtime_profile.return_value = mock.Mock(
                recipient_organization=self.shipment_recipient_organization
            )
            response = self.recipient_scope_client.patch(
                f"/api/v1/ui/portal/recipients/{self.shipment_recipient_organization.id}/",
                {
                    "destination_id": self.destination.id,
                    "structure_name": "UI Recipient Updated",
                    "contact_title": AssociationContactTitle.MRS,
                    "contact_last_name": "Diallo",
                    "contact_first_name": "Aicha",
                    "phones": "0100000001",
                    "emails": "aicha.diallo@example.org",
                    "address_line1": "3 Rue Test",
                    "postal_code": "75003",
                    "city": "Paris",
                    "country": "France",
                    "notify_deliveries": False,
                    "is_delivery_contact": False,
                },
                format="json",
            )

        self.assertEqual(response.status_code, 200)
        update_runtime_profile.assert_called_once()

    def test_ui_portal_recipient_get_returns_persisted_flags_for_recipient_scope(self):
        AssociationRecipient.objects.create(
            association_contact=self.association_contact,
            synced_contact=self.shipment_recipient_organization.organization,
            destination=self.destination,
            structure_name=self.shipment_recipient_organization.organization.name,
            notify_deliveries=True,
            is_delivery_contact=True,
            is_active=True,
        )

        response = self.recipient_scope_client.get(
            f"/api/v1/ui/portal/recipients/{self.shipment_recipient_organization.id}/"
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["recipient"]["notify_deliveries"])
        self.assertTrue(response.json()["recipient"]["is_delivery_contact"])

    def test_ui_portal_recipient_patch_persists_flags_for_recipient_scope(self):
        recipient = AssociationRecipient.objects.create(
            association_contact=self.association_contact,
            synced_contact=self.shipment_recipient_organization.organization,
            destination=self.destination,
            structure_name=self.shipment_recipient_organization.organization.name,
            notify_deliveries=False,
            is_delivery_contact=False,
            is_active=True,
        )

        response = self.recipient_scope_client.patch(
            f"/api/v1/ui/portal/recipients/{self.shipment_recipient_organization.id}/",
            {
                "destination_id": self.destination.id,
                "structure_name": "UI Recipient Updated",
                "contact_title": AssociationContactTitle.MRS,
                "contact_last_name": "Diallo",
                "contact_first_name": "Aicha",
                "phones": "0100000001",
                "emails": "aicha.diallo@example.org",
                "address_line1": "3 Rue Test",
                "postal_code": "75003",
                "city": "Paris",
                "country": "France",
                "notify_deliveries": True,
                "is_delivery_contact": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        recipient.refresh_from_db()
        self.assertTrue(recipient.notify_deliveries)
        self.assertTrue(recipient.is_delivery_contact)
        self.assertTrue(response.json()["recipient"]["notify_deliveries"])
        self.assertTrue(response.json()["recipient"]["is_delivery_contact"])

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

    def test_ui_portal_account_patch_uses_shared_account_use_case(self):
        with mock.patch(
            "api.v1.ui_views.save_portal_account_profile",
            create=True,
        ) as save_profile:
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
        save_profile.assert_called_once()

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

        refreshed_list = self.staff_client.get(
            f"/api/v1/ui/shipments/{self.shipment.id}/documents/"
        )
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
        self.assertIn(
            f"/scan/shipment/{self.shipment.id}/labels/{carton_a.id}/",
            detail_response.json()["url"],
        )

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
                "layout": {"blocks": [{"id": "text-1", "type": "text", "text": "template custom"}]},
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
                "layout": {"blocks": [{"id": "text-1", "type": "text", "text": "template custom"}]},
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
                self._shipment_mutation_payload(lines=[{"product_code": self.product.sku}]),
                "json",
            ),
            (
                "patch",
                f"/api/v1/ui/shipments/{self.shipment.id}/",
                self._shipment_mutation_payload(lines=[{"carton_id": self.available_carton.id}]),
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
