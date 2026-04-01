from datetime import date, datetime, timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from contacts.models import Contact
from wms.models import (
    Carton,
    CartonItem,
    CartonStatus,
    CartonStatusEvent,
    Destination,
    IntegrationDirection,
    IntegrationEvent,
    IntegrationStatus,
    Location,
    Order,
    OrderReviewStatus,
    OrderStatus,
    Product,
    ProductCategory,
    ProductLot,
    ProductLotStatus,
    Receipt,
    ReceiptStatus,
    ReceiptType,
    Shipment,
    ShipmentStatus,
    ShipmentTrackingEvent,
    ShipmentTrackingStatus,
    ShipmentUnitEquivalenceRule,
    ShipmentWorkflowProjection,
    Warehouse,
    WmsRuntimeSettings,
    WorkflowBlockageClaim,
)


class ScanDashboardViewTests(TestCase):
    def setUp(self):
        self.staff_user = get_user_model().objects.create_user(
            username="scan-dashboard-staff",
            password="pass1234",
            is_staff=True,
        )
        self.superuser = get_user_model().objects.create_superuser(
            username="scan-dashboard-admin",
            password="pass1234",
            email="scan-dashboard-admin@example.com",
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

    def _update_instance(self, instance, **updates):
        instance.__class__.objects.filter(pk=instance.pk).update(**updates)
        instance.refresh_from_db()

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
        shipment = self._create_shipment(
            destination=destination,
            status=shipment_status,
            reference=reference,
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
        Order.objects.filter(pk=approved.pk).update(created_at=timezone.now() - timedelta(hours=90))

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
        IntegrationEvent.objects.create(
            direction=IntegrationDirection.OUTBOUND,
            source="wms.document_scan",
            target="antivirus",
            event_type="scan_document",
            payload={"document_id": 1},
            status=IntegrationStatus.PENDING,
        )
        scan_processing_fresh = IntegrationEvent.objects.create(
            direction=IntegrationDirection.OUTBOUND,
            source="wms.document_scan",
            target="antivirus",
            event_type="scan_document",
            payload={"document_id": 2},
            status=IntegrationStatus.PROCESSING,
        )
        scan_processing_stale = IntegrationEvent.objects.create(
            direction=IntegrationDirection.OUTBOUND,
            source="wms.document_scan",
            target="antivirus",
            event_type="scan_document",
            payload={"document_id": 3},
            status=IntegrationStatus.PROCESSING,
        )
        IntegrationEvent.objects.filter(pk=scan_processing_fresh.pk).update(
            processed_at=timezone.now() - timedelta(minutes=5)
        )
        IntegrationEvent.objects.filter(pk=scan_processing_stale.pk).update(
            processed_at=timezone.now() - timedelta(minutes=20)
        )
        IntegrationEvent.objects.create(
            direction=IntegrationDirection.OUTBOUND,
            source="wms.document_scan",
            target="antivirus",
            event_type="scan_document",
            payload={"document_id": 4},
            status=IntegrationStatus.FAILED,
            error_message="ClamAV error",
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

        document_scan_cards = {
            card["label"]: card["value"] for card in response.context["document_scan_cards"]
        }
        self.assertEqual(document_scan_cards["Queue scan doc en attente"], 1)
        self.assertEqual(document_scan_cards["Queue scan doc en traitement"], 2)
        self.assertEqual(document_scan_cards["Queue scan doc en échec"], 1)
        self.assertEqual(document_scan_cards["Queue scan doc bloquée (timeout)"], 1)

        workflow_cards = {
            card["label"]: card["value"] for card in response.context["workflow_blockage_cards"]
        }
        self.assertEqual(workflow_cards["Expéditions Création/En cours >72h"], 1)
        self.assertEqual(workflow_cards["Cmd validées sans expédition >72h"], 1)
        self.assertEqual(workflow_cards["Dossiers livrés non clos"], 1)
        self.assertEqual(workflow_cards["Dossiers en litige ouverts"], 1)

        sla_cards = {card["label"]: card["value"] for card in response.context["sla_cards"]}
        self.assertEqual(sla_cards["Planifié -> OK mise à bord >72h"], "0 / 1")
        self.assertEqual(sla_cards["OK mise à bord -> Reçu escale >72h"], "0 / 1")
        self.assertEqual(sla_cards["Reçu escale -> Livré >72h"], "0 / 1")
        self.assertEqual(sla_cards["Planifié -> Livré >216h"], "0 / 1")

        self.assertTrue(response.context["low_stock_rows"])

    def test_scan_dashboard_filters_by_destination(self):
        self._create_workflow_projection(
            reference="EXP-RISK-DEST-A",
            destination=self.destination_a,
            delay_state="persistent",
            has_open_dispute=True,
            active_blockage_category="suivi",
            segment_age_hours=72,
        )
        self._create_workflow_projection(
            reference="EXP-RISK-DEST-B",
            destination=self.destination_b,
            delay_state="critical",
            has_open_dispute=True,
            active_blockage_category="suivi",
            segment_age_hours=120,
        )
        response = self.client.get(
            reverse("scan:scan_dashboard"),
            {"destination": str(self.destination_b.id), "period": "today"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["destination_id"], str(self.destination_b.id))
        self.assertEqual(len(response.context["destination_risk_rows"]), 1)
        self.assertEqual(
            response.context["destination_risk_rows"][0]["destination_id"],
            self.destination_b.id,
        )

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

    def test_scan_dashboard_hides_settings_link_for_non_superuser(self):
        response = self.client.get(reverse("scan:scan_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("scan:scan_kits_view"))
        self.assertContains(response, reverse("scan:scan_prepare_kits"))
        self.assertNotContains(response, reverse("scan:scan_settings"))
        self.assertNotContains(response, reverse("scan:scan_admin_contacts"))
        self.assertNotContains(response, reverse("scan:scan_admin_products"))
        self.assertNotContains(response, reverse("scan:scan_admin_design"))

    def test_scan_dashboard_shows_management_tools_for_superuser(self):
        self.client.force_login(self.superuser)
        response = self.client.get(reverse("scan:scan_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("scan:scan_kits_view"))
        self.assertContains(response, reverse("scan:scan_prepare_kits"))
        self.assertContains(response, reverse("scan:scan_admin_contacts"))
        self.assertContains(response, reverse("scan:scan_import"))
        self.assertContains(response, reverse("scan:scan_print_templates"))
        self.assertContains(response, reverse("scan:scan_product_labels"))
        self.assertContains(response, reverse("scan:scan_out"))
        self.assertContains(response, reverse("scan:scan_billing_settings"))
        self.assertContains(response, reverse("scan:scan_billing_equivalence"))
        self.assertNotContains(response, reverse("scan:scan_settings"))
        self.assertNotContains(response, reverse("scan:scan_admin_products"))
        self.assertNotContains(response, reverse("scan:scan_admin_design"))

    def test_scan_dashboard_uses_runtime_settings_values(self):
        runtime = WmsRuntimeSettings.get_solo()
        runtime.low_stock_threshold = 7
        runtime.tracking_alert_hours = 48
        runtime.workflow_blockage_hours = 96
        runtime.save()

        response = self.client.get(reverse("scan:scan_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["low_stock_threshold"], 7)
        self.assertEqual(response.context["tracking_alert_hours"], 48)
        self.assertEqual(response.context["workflow_blockage_hours"], 96)

        tracking_cards = {
            card["label"]: card["value"] for card in response.context["tracking_cards"]
        }
        self.assertIn("Planifiées sans mise à bord >48h", tracking_cards)

        workflow_cards = {
            card["label"]: card["value"] for card in response.context["workflow_blockage_cards"]
        }
        self.assertIn("Expéditions Création/En cours >96h", workflow_cards)

    def test_scan_dashboard_defaults_kpi_dates_to_current_week(self):
        response = self.client.get(reverse("scan:scan_dashboard"))
        self.assertEqual(response.status_code, 200)

        today = timezone.localdate()
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)

        self.assertEqual(response.context["kpi_start"], week_start.isoformat())
        self.assertEqual(response.context["kpi_end"], week_end.isoformat())

    def test_scan_dashboard_computes_kpis_from_custom_date_window(self):
        target_at = timezone.now() - timedelta(days=10)
        target_date = timezone.localtime(target_at).date().isoformat()

        reserved = Order.objects.create(
            status=OrderStatus.RESERVED,
            review_status=OrderReviewStatus.APPROVED,
            shipper_name="S",
            recipient_name="R",
            destination_address="A",
            created_by=self.staff_user,
        )
        preparing = Order.objects.create(
            status=OrderStatus.PREPARING,
            review_status=OrderReviewStatus.APPROVED,
            shipper_name="S",
            recipient_name="R",
            destination_address="A",
            created_by=self.staff_user,
        )
        pending_review = Order.objects.create(
            review_status=OrderReviewStatus.PENDING,
            shipper_name="S",
            recipient_name="R",
            destination_address="A",
            created_by=self.staff_user,
        )
        changes_requested = Order.objects.create(
            review_status=OrderReviewStatus.CHANGES_REQUESTED,
            shipper_name="S",
            recipient_name="R",
            destination_address="A",
            created_by=self.staff_user,
        )
        for order in (reserved, preparing, pending_review, changes_requested):
            self._update_instance(order, created_at=target_at)

        created_carton = Carton.objects.create(code="CT-KPI-CREATED", status=CartonStatus.DRAFT)
        assigned_carton = Carton.objects.create(
            code="CT-KPI-ASSIGNED", status=CartonStatus.ASSIGNED
        )
        self._update_instance(created_carton, created_at=target_at)
        self._update_instance(assigned_carton, created_at=target_at)

        status_event = CartonStatusEvent.objects.create(
            carton=assigned_carton,
            previous_status=CartonStatus.PACKED,
            new_status=CartonStatus.ASSIGNED,
            created_by=self.staff_user,
        )
        self._update_instance(status_event, created_at=target_at)

        ready_shipment = self._create_shipment(
            destination=self.destination_a,
            status=ShipmentStatus.PACKED,
            reference="EXP-KPI-READY",
        )
        self._update_instance(ready_shipment, ready_at=target_at)

        response = self.client.get(
            reverse("scan:scan_dashboard"),
            {"kpi_start": target_date, "kpi_end": target_date},
        )
        self.assertEqual(response.status_code, 200)

        kpi_cards = {card["label"]: card["value"] for card in response.context["kpi_cards"]}
        self.assertEqual(kpi_cards["Nb Commandes reçues"], 4)
        self.assertEqual(kpi_cards["Nb commandes en traitement"], 2)
        self.assertEqual(kpi_cards["Nb commandes à valider / corriger"], 2)
        self.assertEqual(kpi_cards["Nb Colis créés"], 2)
        self.assertEqual(kpi_cards["Nb Colis affectés"], 1)
        self.assertEqual(kpi_cards["Nb Expéditions prêtes"], 1)

    def test_scan_dashboard_does_not_expose_chart_specific_context_or_controls(self):
        response = self.client.get(reverse("scan:scan_dashboard"))
        self.assertEqual(response.status_code, 200)

        self.assertContains(response, "<h2>KPI</h2>", html=True)
        self.assertContains(response, 'id="id_kpi_start"')
        self.assertContains(response, 'id="id_kpi_end"')
        self.assertNotIn("chart_start", response.context)
        self.assertNotIn("chart_end", response.context)
        self.assertNotIn("shipment_status", response.context)
        self.assertNotIn("shipment_chart_rows", response.context)
        self.assertNotIn("shipments_total", response.context)
        self.assertNotContains(response, 'id="id_chart_start"')
        self.assertNotContains(response, 'id="id_chart_end"')
        self.assertNotContains(response, 'name="shipment_status"')
        self.assertNotContains(response, 'name="period"')

    def test_scan_dashboard_exposes_actions_anchors_and_grouped_sections(self):
        response = self.client.get(reverse("scan:scan_dashboard"))
        self.assertEqual(response.status_code, 200)

        self.assertEqual(
            [item["id"] for item in response.context["dashboard_anchors"]],
            [
                "scan-dashboard-priorities",
                "scan-dashboard-action-queue",
                "scan-dashboard-destination-risk",
                "scan-dashboard-pilotage",
                "scan-dashboard-flow",
                "scan-dashboard-health",
            ],
        )
        self.assertEqual(
            response.context["page_actions"][0]["url"],
            reverse("scan:scan_pack"),
        )
        self.assertEqual(
            response.context["page_actions"][1]["url"],
            reverse("scan:scan_shipment_create"),
        )
        self.assertEqual(len(response.context["priority_cards"]), 6)
        self.assertIn(
            response.context["action_queue_rows"][0]["owner"],
            {"magasin", "qualite", "admin", "portal"},
        )
        self.assertEqual(response.context["flow_sections"][0]["id"], "scan-dashboard-stock")
        self.assertEqual(
            response.context["system_health_sections"][0]["id"],
            "scan-dashboard-technical",
        )
        self.assertEqual(
            response.context["system_health_sections"][1]["id"],
            "scan-dashboard-document-scan",
        )

    def test_scan_dashboard_renders_action_queue_panel(self):
        response = self.client.get(reverse("scan:scan_dashboard"))
        self.assertEqual(response.status_code, 200)

        self.assertContains(response, 'id="scan-dashboard-action-queue"')
        self.assertContains(response, "À traiter maintenant")

    def test_scan_dashboard_renders_document_scan_health_cards(self):
        response = self.client.get(reverse("scan:scan_dashboard"))
        self.assertEqual(response.status_code, 200)

        self.assertContains(response, "Queue scan doc en attente")
        self.assertContains(response, "Queue scan doc en échec")
        self.assertContains(response, "Technique / Scan documentaire")

    def test_scan_dashboard_action_queue_rows_expose_owner_priority_age_and_cta(self):
        response = self.client.get(reverse("scan:scan_dashboard"))
        self.assertEqual(response.status_code, 200)

        action_rows = response.context["action_queue_rows"]
        self.assertGreaterEqual(len(action_rows), 3)
        self.assertTrue(
            {"admin", "magasin", "qualite"}.issubset({row["owner"] for row in action_rows})
        )
        self.assertIn(action_rows[0]["priority"], {"high", "medium", "low"})
        self.assertIn("age_hours", action_rows[0])
        self.assertIn("url", action_rows[0])
        self.assertIn(action_rows[0]["cta_label"], {"Voir le détail", "Ouvrir le dossier"})
        self.assertContains(response, "magasin")
        self.assertContains(response, "qualite")
        self.assertTrue(any(row["cta_label"] for row in action_rows))

    def test_scan_dashboard_exposes_sla_alert_summary_cards_and_rows(self):
        persistent = self._create_shipment(
            destination=self.destination_a,
            status=ShipmentStatus.PLANNED,
            reference="EXP-SLA-PERSISTENT",
        )
        self._create_tracking_event(
            shipment=persistent,
            status=ShipmentTrackingStatus.PLANNED,
            hours_ago=170,
        )
        critical = self._create_shipment(
            destination=self.destination_a,
            status=ShipmentStatus.SHIPPED,
            reference="EXP-SLA-CRITICAL",
        )
        self._create_tracking_event(
            shipment=critical,
            status=ShipmentTrackingStatus.BOARDING_OK,
            hours_ago=250,
        )

        response = self.client.get(reverse("scan:scan_dashboard"))
        self.assertEqual(response.status_code, 200)

        summary_cards = {
            card["label"]: card["value"] for card in response.context["sla_alert_summary_cards"]
        }
        self.assertEqual(summary_cards["Nouveaux retards"], 3)
        self.assertEqual(summary_cards["Retards persistants"], 1)
        self.assertEqual(summary_cards["Retards critiques"], 1)

        rows_by_reference = {row["reference"]: row for row in response.context["sla_alert_rows"]}
        self.assertEqual(
            rows_by_reference["EXP-SLA-PERSISTENT"]["segment"],
            "Planifié -> OK mise à bord",
        )
        self.assertEqual(rows_by_reference["EXP-SLA-PERSISTENT"]["owner"], "magasin")
        self.assertEqual(rows_by_reference["EXP-SLA-PERSISTENT"]["freshness"], "persistent")
        self.assertEqual(rows_by_reference["EXP-SLA-PERSISTENT"]["severity"], "high")
        self.assertGreater(rows_by_reference["EXP-SLA-PERSISTENT"]["delay_hours"], 95)

        self.assertEqual(
            rows_by_reference["EXP-SLA-CRITICAL"]["segment"],
            "OK mise à bord -> Reçu escale",
        )
        self.assertEqual(rows_by_reference["EXP-SLA-CRITICAL"]["owner"], "qualite")
        self.assertEqual(rows_by_reference["EXP-SLA-CRITICAL"]["freshness"], "persistent")
        self.assertEqual(rows_by_reference["EXP-SLA-CRITICAL"]["severity"], "critical")
        self.assertGreater(rows_by_reference["EXP-SLA-CRITICAL"]["delay_hours"], 175)
        self.assertGreater(
            rows_by_reference["EXP-SLA-CRITICAL"]["age_hours"],
            rows_by_reference["EXP-SLA-CRITICAL"]["delay_hours"],
        )
        self.assertEqual(
            rows_by_reference["EXP-SLA-CRITICAL"]["url"],
            reverse("scan:scan_shipment_track", args=[critical.tracking_token]),
        )

        self.assertContains(response, "Alertes SLA")
        self.assertContains(response, "EXP-SLA-CRITICAL")

    def test_scan_dashboard_promotes_sla_alerts_into_action_queue(self):
        critical = self._create_shipment(
            destination=self.destination_a,
            status=ShipmentStatus.RECEIVED_CORRESPONDENT,
            reference="EXP-SLA-ACTION",
        )
        self._create_tracking_event(
            shipment=critical,
            status=ShipmentTrackingStatus.RECEIVED_CORRESPONDENT,
            hours_ago=260,
        )

        response = self.client.get(reverse("scan:scan_dashboard"))
        self.assertEqual(response.status_code, 200)

        action_rows = response.context["action_queue_rows"]
        self.assertGreaterEqual(len(action_rows), 1)
        self.assertEqual(action_rows[0]["reference"], "EXP-SLA-ACTION")
        self.assertEqual(action_rows[0]["owner"], "portal")
        self.assertEqual(action_rows[0]["priority"], "high")
        self.assertTrue(action_rows[0]["url"].endswith(str(critical.tracking_token) + "/"))

    def test_scan_dashboard_exposes_destination_risk_summary_and_rows(self):
        self._create_workflow_projection(
            reference="EXP-RISK-ABJ-1",
            destination=self.destination_a,
            delay_state="persistent",
            has_open_dispute=True,
            active_blockage_category="creation_expedition",
            segment_age_hours=64,
        )
        self._create_workflow_projection(
            reference="EXP-RISK-ABJ-2",
            destination=self.destination_a,
            delay_state="new",
            has_open_dispute=False,
            active_blockage_category="",
            segment_age_hours=22,
        )
        self._create_workflow_projection(
            reference="EXP-RISK-BZV-1",
            destination=self.destination_b,
            delay_state="critical",
            has_open_dispute=True,
            active_blockage_category="suivi",
            segment_age_hours=120,
        )

        response = self.client.get(reverse("scan:scan_dashboard"))
        self.assertEqual(response.status_code, 200)

        summary_cards = {
            card["label"]: card["value"]
            for card in response.context["destination_risk_summary_cards"]
        }
        self.assertEqual(summary_cards["Destinations critiques"], 1)
        self.assertEqual(summary_cards["Destinations avec litiges"], 2)
        self.assertEqual(summary_cards["Plus ancien dossier ouvert"], "120.0h")

        rows = response.context["destination_risk_rows"]
        self.assertEqual(rows[0]["destination_label"], str(self.destination_b))
        self.assertEqual(rows[0]["delayed_shipment_count"], 1)
        self.assertEqual(rows[0]["critical_shipment_count"], 1)
        self.assertEqual(rows[0]["open_dispute_count"], 1)
        self.assertEqual(rows[0]["top_blockage_category"], "Suivi")
        self.assertEqual(rows[0]["oldest_open_segment_age_hours"], 120)
        self.assertEqual(
            rows[0]["url"],
            f"{reverse('scan:scan_shipments_tracking')}?destination={self.destination_b.id}",
        )
        self.assertEqual(rows[0]["cta_label"], "Ouvrir les dossiers")

    def test_scan_dashboard_renders_destination_risk_panel(self):
        self._create_workflow_projection(
            reference="EXP-RISK-HTML-1",
            destination=self.destination_b,
            delay_state="critical",
            has_open_dispute=True,
            active_blockage_category="suivi",
            segment_age_hours=144,
        )

        response = self.client.get(reverse("scan:scan_dashboard"))
        self.assertEqual(response.status_code, 200)

        self.assertContains(response, 'id="scan-dashboard-destination-risk"')
        self.assertContains(response, "Destinations à risque")
        self.assertContains(response, str(self.destination_b))
        self.assertContains(response, "Ouvrir les dossiers")

    def test_scan_dashboard_exposes_destination_risk_week_trend(self):
        current_week_planned_at = timezone.make_aware(datetime(2026, 3, 31, 10, 0))
        previous_week_planned_at = timezone.make_aware(datetime(2026, 3, 24, 10, 0))
        self._create_workflow_projection(
            reference="EXP-RISK-TREND-A-CUR",
            destination=self.destination_a,
            delay_state="persistent",
            has_open_dispute=True,
            active_blockage_category="suivi",
            segment_age_hours=72,
            planned_at=current_week_planned_at,
        )
        self._create_workflow_projection(
            reference="EXP-RISK-TREND-A-PREV",
            destination=self.destination_a,
            delay_state="new",
            has_open_dispute=False,
            active_blockage_category="creation_expedition",
            segment_age_hours=36,
            planned_at=previous_week_planned_at,
        )
        self._create_workflow_projection(
            reference="EXP-RISK-TREND-B-CUR",
            destination=self.destination_b,
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
            response = self.client.get(reverse("scan:scan_dashboard"))

        self.assertEqual(response.status_code, 200)
        rows_by_destination = {
            row["destination_id"]: row for row in response.context["destination_risk_rows"]
        }
        trend_row = rows_by_destination[self.destination_a.id]
        self.assertEqual(trend_row["current_week_label"], "2026-W14")
        self.assertEqual(trend_row["current_week_score"], 2)
        self.assertEqual(trend_row["previous_week_label"], "2026-W13")
        self.assertEqual(trend_row["previous_week_score"], 1)
        self.assertEqual(trend_row["trend_delta"], 1)
        self.assertEqual(trend_row["trend_direction"], "up")
        self.assertEqual(trend_row["trend_label"], "+1")

        missing_previous_row = rows_by_destination[self.destination_b.id]
        self.assertEqual(missing_previous_row["current_week_score"], 3)
        self.assertEqual(missing_previous_row["previous_week_score"], 0)
        self.assertEqual(missing_previous_row["trend_delta"], 3)

    def test_scan_dashboard_renders_destination_risk_week_trend_columns(self):
        current_week_planned_at = timezone.make_aware(datetime(2026, 3, 31, 10, 0))
        previous_week_planned_at = timezone.make_aware(datetime(2026, 3, 24, 10, 0))
        self._create_workflow_projection(
            reference="EXP-RISK-TREND-HTML-CUR",
            destination=self.destination_b,
            delay_state="critical",
            has_open_dispute=True,
            active_blockage_category="suivi",
            segment_age_hours=144,
            planned_at=current_week_planned_at,
        )
        self._create_workflow_projection(
            reference="EXP-RISK-TREND-HTML-PREV",
            destination=self.destination_b,
            delay_state="persistent",
            has_open_dispute=False,
            active_blockage_category="creation_expedition",
            segment_age_hours=48,
            planned_at=previous_week_planned_at,
        )

        with mock.patch(
            "django.utils.timezone.localdate",
            return_value=date(2026, 3, 31),
        ):
            response = self.client.get(reverse("scan:scan_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Semaine")
        self.assertContains(response, "S-1")
        self.assertContains(response, "Tendance")
        self.assertContains(response, "2026-W14")
        self.assertContains(response, "2026-W13")

    def test_scan_dashboard_priority_cards_include_explicit_cta_labels(self):
        response = self.client.get(reverse("scan:scan_dashboard"))
        self.assertEqual(response.status_code, 200)

        self.assertEqual(
            [card["cta_label"] for card in response.context["priority_cards"]],
            [
                "Voir les expéditions prêtes",
                "Traiter les blocages workflow",
                "Ouvrir le suivi expédition",
                "Traiter les litiges",
                "Contrôler le stock",
                "Investiguer la queue email",
            ],
        )

    def test_scan_dashboard_orders_priority_pilotage_flow_and_health_sections(self):
        response = self.client.get(reverse("scan:scan_dashboard"))
        self.assertEqual(response.status_code, 200)

        content = response.content.decode()
        self.assertLess(
            content.index('id="scan-dashboard-priorities"'),
            content.index('id="scan-dashboard-action-queue"'),
        )
        self.assertLess(
            content.index('id="scan-dashboard-action-queue"'),
            content.index('id="scan-dashboard-workflow-blockages"'),
        )
        self.assertLess(
            content.index('id="scan-dashboard-workflow-blockages"'),
            content.index('id="scan-dashboard-destination-risk"'),
        )
        self.assertLess(
            content.index('id="scan-dashboard-destination-risk"'),
            content.index('id="scan-dashboard-pilotage"'),
        )
        self.assertLess(
            content.index('id="scan-dashboard-pilotage"'),
            content.index('id="scan-dashboard-flow"'),
        )
        self.assertLess(
            content.index('id="scan-dashboard-flow"'),
            content.index('id="scan-dashboard-health"'),
        )

    def test_scan_dashboard_renders_six_priority_cards_with_explicit_actions(self):
        response = self.client.get(reverse("scan:scan_dashboard"))
        self.assertEqual(response.status_code, 200)

        self.assertContains(response, "Voir les expéditions prêtes")
        self.assertContains(response, "Traiter les blocages workflow")
        self.assertContains(response, "Contrôler le stock")
        self.assertContains(response, "Investiguer la queue email")

    def test_scan_dashboard_renders_only_kpi_panel_inside_pilotage_block(self):
        response = self.client.get(reverse("scan:scan_dashboard"))
        self.assertEqual(response.status_code, 200)

        content = response.content.decode()
        pilotage_start = content.index('id="scan-dashboard-pilotage"')
        self.assertIn('id="scan-dashboard-kpi-panel"', content[pilotage_start:])
        self.assertNotIn('id="scan-dashboard-chart-panel"', content[pilotage_start:])

    def test_scan_dashboard_exposes_active_pilotage_threshold_context(self):
        runtime = WmsRuntimeSettings.get_solo()
        runtime.tracking_alert_hours = 24
        runtime.workflow_blockage_hours = 48
        runtime.pilotage_dispute_unassigned_hours = 8
        runtime.pilotage_workflow_blockage_unclaimed_hours = 8
        runtime.pilotage_queue_backlog_threshold = 3
        runtime.pilotage_planning_tension_pct = 75
        runtime.pilotage_planning_critical_pct = 90
        runtime.save(
            update_fields=[
                "tracking_alert_hours",
                "workflow_blockage_hours",
                "pilotage_dispute_unassigned_hours",
                "pilotage_workflow_blockage_unclaimed_hours",
                "pilotage_queue_backlog_threshold",
                "pilotage_planning_tension_pct",
                "pilotage_planning_critical_pct",
            ]
        )

        response = self.client.get(reverse("scan:scan_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Seuils actifs")
        self.assertContains(response, "Pilotage tendu")
        self.assertContains(response, "75%")
        self.assertContains(response, "90%")

    def test_scan_dashboard_exposes_workflow_blockage_rows_by_category(self):
        critical_sla = self._create_shipment(
            destination=self.destination_a,
            status=ShipmentStatus.PLANNED,
            reference="EXP-BLOCKAGE-SLA",
        )
        self._create_tracking_event(
            shipment=critical_sla,
            status=ShipmentTrackingStatus.PLANNED,
            hours_ago=240,
        )

        response = self.client.get(reverse("scan:scan_dashboard"))
        self.assertEqual(response.status_code, 200)

        rows = response.context["workflow_blockage_rows"]
        self.assertTrue(rows)
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
        self.assertIn("workflow_blockage_summary_cards", response.context)
        self.assertTrue(
            any(row["category"] == "queue" and row["reference"] == "wms.email" for row in rows)
        )
        self.assertTrue(
            any(
                row["category"] == "suivi"
                and row["reference"] == critical_sla.reference
                and row["owner"] == "magasin"
                for row in rows
            )
        )

    def test_scan_dashboard_can_claim_and_release_workflow_blockage(self):
        initial_response = self.client.get(reverse("scan:scan_dashboard"))
        self.assertEqual(initial_response.status_code, 200)
        blockage_row = next(
            row
            for row in initial_response.context["workflow_blockage_rows"]
            if row["category"] == "commande"
        )

        claim_response = self.client.post(
            reverse("scan:scan_dashboard"),
            {
                "action": "claim_workflow_blockage",
                "blockage_key": blockage_row["blockage_key"],
            },
            follow=True,
        )
        self.assertEqual(claim_response.status_code, 200)
        self.assertTrue(
            WorkflowBlockageClaim.objects.filter(
                blockage_key=blockage_row["blockage_key"],
                claimed_by=self.staff_user,
            ).exists()
        )
        claimed_row = next(
            row
            for row in claim_response.context["workflow_blockage_rows"]
            if row["blockage_key"] == blockage_row["blockage_key"]
        )
        self.assertTrue(claimed_row["is_claimed"])
        self.assertEqual(claimed_row["claimed_by"], self.staff_user.get_username())

        release_response = self.client.post(
            reverse("scan:scan_dashboard"),
            {
                "action": "release_workflow_blockage",
                "blockage_key": blockage_row["blockage_key"],
            },
            follow=True,
        )
        self.assertEqual(release_response.status_code, 200)
        self.assertFalse(
            WorkflowBlockageClaim.objects.filter(blockage_key=blockage_row["blockage_key"]).exists()
        )
        released_row = next(
            row
            for row in release_response.context["workflow_blockage_rows"]
            if row["blockage_key"] == blockage_row["blockage_key"]
        )
        self.assertFalse(released_row["is_claimed"])
