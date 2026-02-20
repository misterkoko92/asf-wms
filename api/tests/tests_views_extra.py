from datetime import datetime
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
        self.assertIsNone(event.processed_at)

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
