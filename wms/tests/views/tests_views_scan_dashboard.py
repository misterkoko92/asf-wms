from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from contacts.models import Contact
from wms.models import (
    Carton,
    CartonStatus,
    Destination,
    IntegrationDirection,
    IntegrationEvent,
    IntegrationStatus,
    Location,
    Order,
    OrderReviewStatus,
    Product,
    ProductLot,
    ProductLotStatus,
    Receipt,
    ReceiptStatus,
    ReceiptType,
    Shipment,
    ShipmentStatus,
    ShipmentTrackingEvent,
    ShipmentTrackingStatus,
    Warehouse,
)


class ScanDashboardViewTests(TestCase):
    def setUp(self):
        self.staff_user = get_user_model().objects.create_user(
            username="scan-dashboard-staff",
            password="pass1234",
            is_staff=True,
        )
        self.client.force_login(self.staff_user)
        self.warehouse = Warehouse.objects.create(name="Main", code="MAIN")
        self.location = Location.objects.create(
            warehouse=self.warehouse,
            zone="A",
            aisle="01",
            shelf="001",
        )
        self.correspondent_a = Contact.objects.create(
            name="Correspondent A",
            is_active=True,
        )
        self.correspondent_b = Contact.objects.create(
            name="Correspondent B",
            is_active=True,
        )
        self.destination_a = Destination.objects.create(
            city="ABIDJAN",
            iata_code="ABJ",
            country="COTE D'IVOIRE",
            correspondent_contact=self.correspondent_a,
            is_active=True,
        )
        self.destination_b = Destination.objects.create(
            city="BRAZZAVILLE",
            iata_code="BZV",
            country="REP. DU CONGO",
            correspondent_contact=self.correspondent_b,
            is_active=True,
        )
        self._create_stock_data()
        self._create_shipment_data()
        self._create_flow_data()
        self._create_carton_data()
        self._create_integration_queue_data()

    def _create_stock_data(self):
        low_product = Product.objects.create(
            sku="SKU-LOW",
            name="Produit Bas",
            is_active=True,
            default_location=self.location,
            qr_code_image="qr_codes/low.png",
        )
        high_product = Product.objects.create(
            sku="SKU-HIGH",
            name="Produit Haut",
            is_active=True,
            default_location=self.location,
            qr_code_image="qr_codes/high.png",
        )
        ProductLot.objects.create(
            product=low_product,
            lot_code="LOW-LOT",
            status=ProductLotStatus.AVAILABLE,
            quantity_on_hand=5,
            quantity_reserved=0,
            location=self.location,
        )
        ProductLot.objects.create(
            product=high_product,
            lot_code="HIGH-LOT",
            status=ProductLotStatus.AVAILABLE,
            quantity_on_hand=50,
            quantity_reserved=5,
            location=self.location,
        )

    def _create_shipment(
        self,
        *,
        destination,
        status,
        reference="",
        is_disputed=False,
    ):
        return Shipment.objects.create(
            reference=reference,
            status=status,
            shipper_name="Shipper",
            recipient_name="Recipient",
            correspondent_name="Correspondent",
            destination=destination,
            destination_address=str(destination),
            destination_country=destination.country,
            created_by=self.staff_user,
            is_disputed=is_disputed,
        )

    def _create_tracking_event(self, *, shipment, status, hours_ago):
        event = ShipmentTrackingEvent.objects.create(
            shipment=shipment,
            status=status,
            actor_name="Actor",
            actor_structure="Structure",
            comments="",
            created_by=self.staff_user,
        )
        ShipmentTrackingEvent.objects.filter(pk=event.pk).update(
            created_at=timezone.now() - timedelta(hours=hours_ago)
        )

    def _create_shipment_data(self):
        self.draft_temp = self._create_shipment(
            destination=self.destination_a,
            status=ShipmentStatus.DRAFT,
            reference="EXP-TEMP-01",
        )
        self.picking_b = self._create_shipment(
            destination=self.destination_b,
            status=ShipmentStatus.PICKING,
        )
        self.packed_a = self._create_shipment(
            destination=self.destination_a,
            status=ShipmentStatus.PACKED,
        )
        self.planned_alert_a = self._create_shipment(
            destination=self.destination_a,
            status=ShipmentStatus.PLANNED,
        )
        self._create_tracking_event(
            shipment=self.planned_alert_a,
            status=ShipmentTrackingStatus.PLANNED,
            hours_ago=80,
        )

        self.shipped_alert_a = self._create_shipment(
            destination=self.destination_a,
            status=ShipmentStatus.SHIPPED,
        )
        self._create_tracking_event(
            shipment=self.shipped_alert_a,
            status=ShipmentTrackingStatus.BOARDING_OK,
            hours_ago=80,
        )

        self.correspondent_alert_a = self._create_shipment(
            destination=self.destination_a,
            status=ShipmentStatus.RECEIVED_CORRESPONDENT,
        )
        self._create_tracking_event(
            shipment=self.correspondent_alert_a,
            status=ShipmentTrackingStatus.RECEIVED_CORRESPONDENT,
            hours_ago=80,
        )

        self.closable_a = self._create_shipment(
            destination=self.destination_a,
            status=ShipmentStatus.DELIVERED,
        )
        self._create_tracking_event(
            shipment=self.closable_a,
            status=ShipmentTrackingStatus.PLANNED,
            hours_ago=20,
        )
        self._create_tracking_event(
            shipment=self.closable_a,
            status=ShipmentTrackingStatus.BOARDING_OK,
            hours_ago=18,
        )
        self._create_tracking_event(
            shipment=self.closable_a,
            status=ShipmentTrackingStatus.RECEIVED_CORRESPONDENT,
            hours_ago=12,
        )
        self._create_tracking_event(
            shipment=self.closable_a,
            status=ShipmentTrackingStatus.RECEIVED_RECIPIENT,
            hours_ago=2,
        )

        self.disputed_a = self._create_shipment(
            destination=self.destination_a,
            status=ShipmentStatus.PLANNED,
            is_disputed=True,
        )
        Shipment.objects.filter(pk=self.draft_temp.pk).update(
            created_at=timezone.now() - timedelta(hours=90)
        )

    def _create_flow_data(self):
        Receipt.objects.create(
            receipt_type=ReceiptType.DONATION,
            status=ReceiptStatus.DRAFT,
            warehouse=self.warehouse,
            created_by=self.staff_user,
        )
        Order.objects.create(
            review_status=OrderReviewStatus.PENDING,
            shipper_name="S",
            recipient_name="R",
            destination_address="A",
            created_by=self.staff_user,
        )
        Order.objects.create(
            review_status=OrderReviewStatus.CHANGES_REQUESTED,
            shipper_name="S",
            recipient_name="R",
            destination_address="A",
            created_by=self.staff_user,
        )
        approved = Order.objects.create(
            review_status=OrderReviewStatus.APPROVED,
            shipper_name="S",
            recipient_name="R",
            destination_address="A",
            created_by=self.staff_user,
        )
        Order.objects.filter(pk=approved.pk).update(
            created_at=timezone.now() - timedelta(hours=90)
        )

    def _create_carton_data(self):
        Carton.objects.create(code="CT-PICK", status=CartonStatus.PICKING)
        Carton.objects.create(code="CT-PACK", status=CartonStatus.PACKED)
        Carton.objects.create(
            code="CT-ASSIGNED",
            status=CartonStatus.ASSIGNED,
            shipment=self.planned_alert_a,
        )
        Carton.objects.create(
            code="CT-LABELED",
            status=CartonStatus.LABELED,
            shipment=self.planned_alert_a,
        )
        Carton.objects.create(
            code="CT-SHIPPED",
            status=CartonStatus.SHIPPED,
            shipment=self.shipped_alert_a,
        )

    def _create_integration_queue_data(self):
        IntegrationEvent.objects.create(
            direction=IntegrationDirection.OUTBOUND,
            source="wms.email",
            target="smtp",
            event_type="send_email",
            payload={"subject": "Pending"},
            status=IntegrationStatus.PENDING,
        )
        processing = IntegrationEvent.objects.create(
            direction=IntegrationDirection.OUTBOUND,
            source="wms.email",
            target="smtp",
            event_type="send_email",
            payload={"subject": "Processing"},
            status=IntegrationStatus.PROCESSING,
        )
        IntegrationEvent.objects.filter(pk=processing.pk).update(
            processed_at=timezone.now() - timedelta(minutes=20)
        )
        IntegrationEvent.objects.create(
            direction=IntegrationDirection.OUTBOUND,
            source="wms.email",
            target="smtp",
            event_type="send_email",
            payload={"subject": "Failed"},
            status=IntegrationStatus.FAILED,
            error_message="SMTP error",
        )
        IntegrationEvent.objects.create(
            direction=IntegrationDirection.OUTBOUND,
            source="wms.email",
            target="smtp",
            event_type="send_email",
            payload={"subject": "Processed"},
            status=IntegrationStatus.PROCESSED,
        )

    def test_scan_dashboard_renders_expected_metrics(self):
        response = self.client.get(reverse("scan:scan_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["active"], "dashboard")
        self.assertEqual(response.context["low_stock_threshold"], 20)
        self.assertEqual(response.context["tracking_alert_hours"], 72)
        self.assertEqual(response.context["workflow_blockage_hours"], 72)

        shipment_cards = {
            card["label"]: card["value"] for card in response.context["shipment_cards"]
        }
        self.assertEqual(shipment_cards["Brouillons"], 1)
        self.assertEqual(shipment_cards["En cours"], 1)
        self.assertEqual(shipment_cards["Prêtes"], 1)
        self.assertEqual(shipment_cards["Litiges ouverts"], 1)

        tracking_cards = {
            card["label"]: card["value"] for card in response.context["tracking_cards"]
        }
        self.assertEqual(tracking_cards["Planifiées sans mise à bord >72h"], 1)
        self.assertEqual(tracking_cards["Expédiées sans reçu escale >72h"], 1)
        self.assertEqual(tracking_cards["Reçu escale sans livraison >72h"], 1)
        self.assertEqual(tracking_cards["Dossiers clôturables"], 1)

        technical_cards = {
            card["label"]: card["value"] for card in response.context["technical_cards"]
        }
        self.assertEqual(technical_cards["Queue email en attente"], 1)
        self.assertEqual(technical_cards["Queue email en traitement"], 1)
        self.assertEqual(technical_cards["Queue email en échec"], 1)
        self.assertEqual(technical_cards["Queue email bloquée (timeout)"], 1)

        workflow_cards = {
            card["label"]: card["value"]
            for card in response.context["workflow_blockage_cards"]
        }
        self.assertEqual(workflow_cards["Expéditions Création/En cours >72h"], 1)
        self.assertEqual(workflow_cards["Cmd validées sans expédition >72h"], 1)
        self.assertEqual(workflow_cards["Dossiers livrés non clos"], 1)
        self.assertEqual(workflow_cards["Dossiers en litige ouverts"], 1)

        sla_cards = {
            card["label"]: card["value"] for card in response.context["sla_cards"]
        }
        self.assertEqual(sla_cards["Planifié -> OK mise à bord >72h"], "0 / 1")
        self.assertEqual(sla_cards["OK mise à bord -> Reçu escale >72h"], "0 / 1")
        self.assertEqual(sla_cards["Reçu escale -> Livré >72h"], "0 / 1")
        self.assertEqual(sla_cards["Planifié -> Livré >216h"], "0 / 1")

        self.assertEqual(response.context["shipments_total"], 8)
        self.assertTrue(response.context["low_stock_rows"])

    def test_scan_dashboard_filters_by_destination(self):
        response = self.client.get(
            reverse("scan:scan_dashboard"),
            {"destination": str(self.destination_b.id), "period": "today"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["destination_id"], str(self.destination_b.id))
        self.assertEqual(response.context["shipments_total"], 1)

        shipment_cards = {
            card["label"]: card["value"] for card in response.context["shipment_cards"]
        }
        self.assertEqual(shipment_cards["En cours"], 1)
        self.assertEqual(shipment_cards["Brouillons"], 0)

    def test_scan_dashboard_requires_staff(self):
        non_staff = get_user_model().objects.create_user(
            username="scan-dashboard-non-staff",
            password="pass1234",
            is_staff=False,
        )
        self.client.force_login(non_staff)
        response = self.client.get(reverse("scan:scan_dashboard"))
        self.assertEqual(response.status_code, 403)
