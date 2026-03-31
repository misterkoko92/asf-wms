from datetime import datetime, timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from contacts.models import Contact
from wms.domain.stock import StockError
from wms.models import (
    Destination,
    IntegrationDirection,
    IntegrationEvent,
    IntegrationStatus,
    Location,
    Order,
    OrderLine,
    OrderStatus,
    Product,
    Shipment,
    ShipmentTrackingEvent,
    ShipmentTrackingStatus,
    ShipmentWorkflowProjection,
    Warehouse,
)


@override_settings(INTEGRATION_API_KEY="test-key")
class ApiViewsExtraTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="api-extra-user",
            password="pass1234",
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.integration_client = APIClient()
        self.integration_headers = {"HTTP_X_ASF_INTEGRATION_KEY": "test-key"}

        self.warehouse = Warehouse.objects.create(name="API Extra WH", code="APIX")
        self.location = Location.objects.create(
            warehouse=self.warehouse,
            zone="A",
            aisle="01",
            shelf="001",
        )
        self.product = Product.objects.create(
            sku="API-EXTRA-001",
            name="API Extra Product",
            default_location=self.location,
        )
        self.contact = Contact.objects.create(name="API Contact")

    def _create_order(self):
        order = Order.objects.create(
            status=OrderStatus.DRAFT,
            shipper_name="Sender",
            recipient_name="Recipient",
            correspondent_name="Correspondent",
            destination_address="10 Rue Test",
            destination_country="France",
            created_by=self.user,
        )
        OrderLine.objects.create(order=order, product=self.product, quantity=2)
        return order

    def _create_workflow_projection(
        self,
        *,
        reference,
        destination,
        shipment_status="planned",
        current_segment="planned_to_boarding",
        delay_state="on_time",
        has_open_dispute=False,
        is_closed=False,
        active_blockage_category="",
        segment_age_hours=0.0,
        lead_hours_total_to_delivery=None,
        lead_hours_delivery_to_close=None,
    ):
        shipment = Shipment.objects.create(
            reference=reference,
            status=shipment_status,
            shipper_name="Sender",
            recipient_name="Recipient",
            correspondent_name="Correspondent",
            destination=destination,
            destination_address=f"{destination.city} Projection",
            destination_country=destination.country,
            created_by=self.user,
        )
        started_at = timezone.now() - timedelta(hours=segment_age_hours)
        return ShipmentWorkflowProjection.objects.create(
            shipment=shipment,
            destination=destination,
            reference=shipment.reference,
            tracking_token=shipment.tracking_token,
            destination_label=str(destination),
            shipment_status=shipment_status,
            current_segment=current_segment,
            segment_started_at=started_at,
            segment_age_hours=segment_age_hours,
            is_closed=is_closed,
            has_open_dispute=has_open_dispute,
            delay_state=delay_state,
            active_blockage_category=active_blockage_category,
            lead_hours_total_to_delivery=lead_hours_total_to_delivery,
            lead_hours_delivery_to_close=lead_hours_delivery_to_close,
        )

    def test_order_reserve_returns_400_on_stock_error(self):
        order = self._create_order()
        with mock.patch(
            "api.v1.views.reserve_stock_for_order",
            side_effect=StockError("reserve failed"),
        ):
            response = self.client.post(f"/api/v1/orders/{order.id}/reserve/")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "reserve failed")

    def test_order_prepare_returns_400_on_stock_error(self):
        order = self._create_order()
        with mock.patch(
            "api.v1.views.prepare_order",
            side_effect=StockError("prepare failed"),
        ):
            response = self.client.post(f"/api/v1/orders/{order.id}/prepare/")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "prepare failed")

    def test_receive_stock_returns_400_on_domain_error(self):
        payload = {
            "product_id": self.product.id,
            "quantity": 5,
            "location_id": self.location.id,
        }
        with mock.patch(
            "api.v1.views.receive_stock_from_input",
            side_effect=ValueError("invalid payload"),
        ):
            response = self.client.post("/api/v1/stock/receive/", payload, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "invalid payload")

    def test_pack_carton_returns_400_on_domain_error(self):
        payload = {
            "product_id": self.product.id,
            "quantity": 2,
        }
        with mock.patch(
            "api.v1.views.pack_carton_from_input",
            side_effect=StockError("pack failed"),
        ):
            response = self.client.post("/api/v1/pack/", payload, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "pack failed")

    def test_pack_carton_rejects_carton_id_and_code_at_once(self):
        payload = {
            "product_id": self.product.id,
            "quantity": 2,
            "carton_id": 1,
            "carton_code": "C-01",
        }
        response = self.client.post("/api/v1/pack/", payload, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertIn("non_field_errors", response.json())

    def test_integration_destinations_active_filter_and_ordering(self):
        destination_a = Destination.objects.create(
            city="Zurich",
            iata_code="ZRH",
            country="Switzerland",
            correspondent_contact=self.contact,
            is_active=True,
        )
        destination_b = Destination.objects.create(
            city="Abidjan",
            iata_code="ABJ",
            country="Cote d'Ivoire",
            correspondent_contact=self.contact,
            is_active=True,
        )
        Destination.objects.create(
            city="Lyon",
            iata_code="LYS",
            country="France",
            correspondent_contact=self.contact,
            is_active=False,
        )

        response = self.integration_client.get(
            "/api/v1/integrations/destinations/?active=1",
            **self.integration_headers,
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual([row["city"] for row in data], ["Abidjan", "Zurich"])
        ids = [row["id"] for row in data]
        self.assertIn(destination_a.id, ids)
        self.assertIn(destination_b.id, ids)

    def test_integration_events_list_applies_filters(self):
        matched = IntegrationEvent.objects.create(
            direction=IntegrationDirection.INBOUND,
            source="sync",
            target="wms",
            event_type="shipment.created",
            status=IntegrationStatus.PENDING,
        )
        IntegrationEvent.objects.create(
            direction=IntegrationDirection.INBOUND,
            source="sync",
            target="wms",
            event_type="shipment.created",
            status=IntegrationStatus.FAILED,
        )

        response = self.integration_client.get(
            "/api/v1/integrations/events/?status=pending&source=sync",
            **self.integration_headers,
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["id"], matched.id)

    def test_integration_event_create_uses_headers_for_source_and_target(self):
        payload = {
            "event_type": "shipment.created",
            "payload": {"reference": "SHP-1"},
        }
        response = self.integration_client.post(
            "/api/v1/integrations/events/",
            payload,
            format="json",
            HTTP_X_ASF_INTEGRATION_KEY="test-key",
            HTTP_X_ASF_SOURCE=" scheduler ",
            HTTP_X_ASF_TARGET=" external ",
        )

        self.assertEqual(response.status_code, 201)
        event = IntegrationEvent.objects.get()
        self.assertEqual(event.source, "scheduler")
        self.assertEqual(event.target, "external")
        self.assertEqual(event.direction, IntegrationDirection.INBOUND)
        self.assertEqual(event.status, IntegrationStatus.PENDING)

    def test_integration_event_create_requires_source(self):
        payload = {"event_type": "shipment.created", "payload": {}}
        response = self.integration_client.post(
            "/api/v1/integrations/events/",
            payload,
            format="json",
            **self.integration_headers,
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("source", response.json())

    def test_integration_event_partial_update_sets_processed_at(self):
        event = IntegrationEvent.objects.create(
            direction=IntegrationDirection.INBOUND,
            source="sync",
            target="wms",
            event_type="shipment.created",
            status=IntegrationStatus.PENDING,
        )
        fixed_now = timezone.make_aware(datetime(2026, 1, 20, 15, 30, 0))

        with mock.patch("api.v1.views.timezone.now", return_value=fixed_now):
            response = self.integration_client.patch(
                f"/api/v1/integrations/events/{event.id}/",
                {"status": IntegrationStatus.PROCESSED},
                format="json",
                **self.integration_headers,
            )

        self.assertEqual(response.status_code, 200)
        event.refresh_from_db()
        self.assertEqual(event.status, IntegrationStatus.PROCESSED)
        self.assertEqual(event.processed_at, fixed_now)

    def test_integration_event_partial_update_uses_default_save_path(self):
        event = IntegrationEvent.objects.create(
            direction=IntegrationDirection.INBOUND,
            source="sync",
            target="wms",
            event_type="shipment.created",
            status=IntegrationStatus.PENDING,
        )
        response = self.integration_client.patch(
            f"/api/v1/integrations/events/{event.id}/",
            {"status": IntegrationStatus.FAILED, "error_message": "boom"},
            format="json",
            **self.integration_headers,
        )

        self.assertEqual(response.status_code, 200)
        event.refresh_from_db()
        self.assertEqual(event.status, IntegrationStatus.FAILED)
        self.assertEqual(event.error_message, "boom")

    def test_workflow_projections_shipments_endpoint_returns_projected_rows(self):
        destination = Destination.objects.create(
            city="Niamey",
            iata_code="NIM",
            country="Niger",
            correspondent_contact=self.contact,
            is_active=True,
        )
        shipment = Shipment.objects.create(
            reference="EXP-API-PROJ-001",
            status="planned",
            shipper_name="Sender",
            recipient_name="Recipient",
            correspondent_name="Correspondent",
            destination=destination,
            destination_address="12 Rue Projection",
            destination_country=destination.country,
            created_by=self.user,
        )
        tracking_event = ShipmentTrackingEvent.objects.create(
            shipment=shipment,
            status=ShipmentTrackingStatus.PLANNED,
            actor_name="Ops",
            actor_structure="ASF",
            created_by=self.user,
        )
        ShipmentTrackingEvent.objects.filter(pk=tracking_event.pk).update(
            created_at=timezone.now() - timedelta(hours=96)
        )
        ShipmentWorkflowProjection.objects.create(
            shipment=shipment,
            reference=shipment.reference,
            tracking_token=shipment.tracking_token,
            destination_id=destination.id,
            destination_label=str(destination),
            shipment_status=shipment.status,
            shipment_created_at=shipment.created_at,
            planned_at=timezone.now() - timedelta(hours=96),
            current_segment="planned_to_boarding",
            segment_started_at=timezone.now() - timedelta(hours=96),
            segment_age_hours=96,
            is_closed=False,
            delay_state="new",
            current_delay_hours=24,
            active_blockage_category="suivi",
        )

        response = self.client.get("/api/v1/workflow-projections/shipments/")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["reference"], shipment.reference)
        self.assertEqual(data[0]["current_segment"], "planned_to_boarding")
        self.assertEqual(data[0]["delay_state"], "new")

    def test_workflow_projections_shipments_endpoint_applies_filters(self):
        destination = Destination.objects.create(
            city="Lome",
            iata_code="LFW",
            country="Togo",
            correspondent_contact=self.contact,
            is_active=True,
        )
        projection = ShipmentWorkflowProjection.objects.create(
            shipment=Shipment.objects.create(
                reference="EXP-API-PROJ-002",
                status="delivered",
                shipper_name="Sender",
                recipient_name="Recipient",
                correspondent_name="Correspondent",
                destination=destination,
                destination_address="14 Rue Projection",
                destination_country="Togo",
                created_by=self.user,
            ),
            reference="EXP-API-PROJ-002",
            destination=destination,
            shipment_status="delivered",
            current_segment="delivery_to_close",
            delay_state="persistent",
            has_open_dispute=True,
            is_closed=False,
        )

        response = self.client.get(
            "/api/v1/workflow-projections/shipments/?delay_state=persistent&has_open_dispute=1&is_closed=0"
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["reference"], projection.reference)

    def test_workflow_projections_destinations_endpoint_returns_aggregated_rows(self):
        critical_destination = Destination.objects.create(
            city="Dakar",
            iata_code="DKR",
            country="Senegal",
            correspondent_contact=self.contact,
            is_active=True,
        )
        secondary_destination = Destination.objects.create(
            city="Bamako",
            iata_code="BKO",
            country="Mali",
            correspondent_contact=self.contact,
            is_active=True,
        )

        self._create_workflow_projection(
            reference="EXP-DEST-001",
            destination=critical_destination,
            shipment_status="shipped",
            current_segment="boarding_to_correspondent",
            delay_state="critical",
            has_open_dispute=True,
            active_blockage_category="suivi",
            segment_age_hours=144.0,
            lead_hours_total_to_delivery=120.0,
        )
        self._create_workflow_projection(
            reference="EXP-DEST-002",
            destination=critical_destination,
            shipment_status="draft",
            current_segment="creation_expedition",
            delay_state="new",
            active_blockage_category="creation_expedition",
            segment_age_hours=80.0,
        )
        self._create_workflow_projection(
            reference="EXP-DEST-003",
            destination=critical_destination,
            shipment_status="delivered",
            current_segment="closed",
            delay_state="on_time",
            is_closed=True,
            segment_age_hours=0.0,
            lead_hours_total_to_delivery=48.0,
            lead_hours_delivery_to_close=12.0,
        )
        self._create_workflow_projection(
            reference="EXP-DEST-004",
            destination=secondary_destination,
            shipment_status="delivered",
            current_segment="delivery_to_close",
            delay_state="persistent",
            active_blockage_category="cloture",
            segment_age_hours=100.0,
            lead_hours_total_to_delivery=72.0,
        )

        response = self.client.get("/api/v1/workflow-projections/destinations/")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 2)

        first_row = data[0]
        self.assertEqual(first_row["destination_id"], critical_destination.id)
        self.assertEqual(first_row["shipment_count"], 3)
        self.assertEqual(first_row["open_shipment_count"], 2)
        self.assertEqual(first_row["closed_shipment_count"], 1)
        self.assertEqual(first_row["open_dispute_count"], 1)
        self.assertEqual(first_row["delayed_shipment_count"], 2)
        self.assertEqual(first_row["critical_shipment_count"], 1)
        self.assertEqual(first_row["creation_blockage_count"], 1)
        self.assertEqual(first_row["tracking_blockage_count"], 1)
        self.assertEqual(first_row["closure_blockage_count"], 0)
        self.assertEqual(first_row["avg_total_to_delivery_hours"], 84.0)
        self.assertEqual(first_row["avg_delivery_to_close_hours"], 12.0)
        self.assertEqual(first_row["oldest_open_segment_age_hours"], 144.0)
        self.assertEqual(first_row["top_delay_state"], "critical")
        self.assertEqual(first_row["top_blockage_category"], "suivi")
        self.assertTrue(first_row["projected_at_max"])

    def test_workflow_projections_destinations_endpoint_applies_filters_before_grouping(self):
        filtered_destination = Destination.objects.create(
            city="Lome",
            iata_code="LFW",
            country="Togo",
            correspondent_contact=self.contact,
            is_active=True,
        )
        excluded_destination = Destination.objects.create(
            city="Niamey",
            iata_code="NIM",
            country="Niger",
            correspondent_contact=self.contact,
            is_active=True,
        )

        self._create_workflow_projection(
            reference="EXP-FILTER-001",
            destination=filtered_destination,
            shipment_status="delivered",
            current_segment="delivery_to_close",
            delay_state="persistent",
            has_open_dispute=True,
            active_blockage_category="suivi",
            segment_age_hours=90.0,
        )
        self._create_workflow_projection(
            reference="EXP-FILTER-002",
            destination=filtered_destination,
            shipment_status="planned",
            current_segment="planned_to_boarding",
            delay_state="on_time",
            has_open_dispute=False,
            active_blockage_category="",
            segment_age_hours=10.0,
        )
        self._create_workflow_projection(
            reference="EXP-FILTER-003",
            destination=excluded_destination,
            shipment_status="delivered",
            current_segment="delivery_to_close",
            delay_state="persistent",
            has_open_dispute=False,
            active_blockage_category="cloture",
            segment_age_hours=120.0,
        )

        response = self.client.get(
            "/api/v1/workflow-projections/destinations/?delay_state=persistent&has_open_dispute=1&is_closed=0"
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["destination_id"], filtered_destination.id)
        self.assertEqual(data[0]["shipment_count"], 1)
        self.assertEqual(data[0]["open_shipment_count"], 1)
        self.assertEqual(data[0]["open_dispute_count"], 1)
        self.assertEqual(data[0]["delayed_shipment_count"], 1)
        self.assertEqual(data[0]["tracking_blockage_count"], 1)

    def test_integration_event_partial_update_rejects_outbound_email_queue_event(self):
        event = IntegrationEvent.objects.create(
            direction=IntegrationDirection.OUTBOUND,
            source="wms.email",
            target="smtp",
            event_type="send_email",
            status=IntegrationStatus.PENDING,
            payload={"subject": "Test", "recipient": ["ops@example.com"]},
        )
        response = self.integration_client.patch(
            f"/api/v1/integrations/events/{event.id}/",
            {"status": IntegrationStatus.PROCESSED},
            format="json",
            **self.integration_headers,
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("detail", response.json())
        event.refresh_from_db()
        self.assertEqual(event.status, IntegrationStatus.PENDING)
        self.assertIsNone(event.processed_at)
