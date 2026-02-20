from django.contrib.auth import get_user_model
from django.test import TestCase

from contacts.models import Contact
from wms.models import (
    AssociationRecipient,
    Destination,
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

    def test_delivered_status_queues_delivery_notification_for_opted_recipients(self):
        association_contact = Contact.objects.create(
            name="Association Notify Deliveries",
        )
        destination = Destination.objects.create(
            city="Lyon",
            iata_code="LYS",
            country="France",
            correspondent_contact=Contact.objects.create(
                name="Correspondent Lyon",
            ),
        )
        other_destination = Destination.objects.create(
            city="Abidjan",
            iata_code="ABJ",
            country="Cote d'Ivoire",
            correspondent_contact=Contact.objects.create(
                name="Correspondent Abidjan",
            ),
        )
        AssociationRecipient.objects.create(
            association_contact=association_contact,
            destination=destination,
            name="Recipient A",
            emails="delivery@example.com; DELIVERY@example.com; second@example.com",
            address_line1="1 Rue A",
            city="Lyon",
            country="France",
            notify_deliveries=True,
            is_active=True,
        )
        AssociationRecipient.objects.create(
            association_contact=association_contact,
            destination=None,
            name="Recipient B",
            email="fallback@example.com",
            address_line1="2 Rue B",
            city="Paris",
            country="France",
            notify_deliveries=True,
            is_active=True,
        )
        AssociationRecipient.objects.create(
            association_contact=association_contact,
            destination=other_destination,
            name="Recipient C",
            email="other-destination@example.com",
            address_line1="3 Rue C",
            city="Abidjan",
            country="Cote d'Ivoire",
            notify_deliveries=True,
            is_active=True,
        )
        AssociationRecipient.objects.create(
            association_contact=association_contact,
            destination=destination,
            name="Recipient D",
            email="disabled-notify@example.com",
            address_line1="4 Rue D",
            city="Lyon",
            country="France",
            notify_deliveries=False,
            is_active=True,
        )
        self.shipment.shipper_contact_ref = association_contact
        self.shipment.destination = destination
        self.shipment.save(update_fields=["shipper_contact_ref", "destination"])

        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            self.shipment.status = ShipmentStatus.DELIVERED
            self.shipment.save(update_fields=["status"])

        self.assertEqual(len(callbacks), 2)
        events = list(
            IntegrationEvent.objects.filter(
                direction=IntegrationDirection.OUTBOUND,
                source="wms.email",
                event_type="send_email",
                status=IntegrationStatus.PENDING,
            )
        )
        self.assertEqual(len(events), 2)
        delivery_subject = (
            f"ASF WMS - Expedition {self.shipment.reference} : livraison confirmee"
        )
        delivery_event = next(
            event for event in events if event.payload.get("subject") == delivery_subject
        )
        self.assertEqual(
            delivery_event.payload.get("recipient"),
            ["delivery@example.com", "second@example.com", "fallback@example.com"],
        )
