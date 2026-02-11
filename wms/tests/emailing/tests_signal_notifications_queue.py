from django.contrib.auth import get_user_model
from django.test import TestCase

from wms.models import (
    IntegrationDirection,
    IntegrationEvent,
    IntegrationStatus,
    Shipment,
    ShipmentStatus,
    ShipmentTrackingEvent,
    ShipmentTrackingStatus,
)


class ShipmentSignalEmailQueueTests(TestCase):
    def setUp(self):
        self.creator = get_user_model().objects.create_user(
            username="shipment-user",
            email="shipment-user@example.com",
            password="pass1234",
        )
        get_user_model().objects.create_superuser(
            username="shipment-admin",
            email="admin@example.com",
            password="pass1234",
        )
        self.shipment = Shipment.objects.create(
            status=ShipmentStatus.DRAFT,
            shipper_name="Sender",
            recipient_name="Recipient",
            correspondent_name="Contact",
            destination_address="10 Rue Test, Paris",
            destination_country="France",
            created_by=self.creator,
        )

    def test_shipment_status_change_queues_email_event(self):
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            self.shipment.status = ShipmentStatus.SHIPPED
            self.shipment.save(update_fields=["status"])

        self.assertEqual(len(callbacks), 1)
        events = IntegrationEvent.objects.filter(
            direction=IntegrationDirection.OUTBOUND,
            source="wms.email",
            event_type="send_email",
            status=IntegrationStatus.PENDING,
        )
        self.assertEqual(events.count(), 1)
        event = events.first()
        self.assertEqual(
            event.payload.get("subject"),
            f"ASF WMS - Expédition {self.shipment.reference} : statut mis à jour",
        )
        self.assertEqual(event.payload.get("recipient"), ["admin@example.com"])

    def test_tracking_event_creation_queues_email_event(self):
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            ShipmentTrackingEvent.objects.create(
                shipment=self.shipment,
                status=ShipmentTrackingStatus.PLANNING_OK,
                actor_name="Test Actor",
                actor_structure="ASF",
                comments="ok",
            )

        self.assertEqual(len(callbacks), 1)
        events = IntegrationEvent.objects.filter(
            direction=IntegrationDirection.OUTBOUND,
            source="wms.email",
            event_type="send_email",
            status=IntegrationStatus.PENDING,
        )
        self.assertEqual(events.count(), 1)
        event = events.first()
        self.assertEqual(
            event.payload.get("subject"),
            f"ASF WMS - Suivi expédition {self.shipment.reference}",
        )
        self.assertEqual(event.payload.get("recipient"), ["admin@example.com"])
