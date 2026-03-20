from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase

from contacts.models import Contact, ContactType
from wms.models import (
    Destination,
    IntegrationDirection,
    IntegrationEvent,
    IntegrationStatus,
    Shipment,
    ShipmentStatus,
    ShipmentTrackingEvent,
    ShipmentTrackingStatus,
)
from wms.shipment_party_snapshot import build_shipment_party_snapshot


class ShipmentPartyNotificationTests(TestCase):
    def setUp(self):
        self.send_email_patcher = mock.patch(
            "wms.emailing.send_email_safe",
            return_value=False,
        )
        self.send_email_patcher.start()
        self.addCleanup(self.send_email_patcher.stop)

        self.creator = get_user_model().objects.create_user(
            username="shipment-party-user",
            email="shipment-party-user@example.com",
            password="pass1234",  # pragma: allowlist secret
        )
        get_user_model().objects.create_superuser(
            username="shipment-party-admin",
            email="admin@example.com",
            password="pass1234",  # pragma: allowlist secret
        )

    def _create_org(self, name: str, *, email: str) -> Contact:
        return Contact.objects.create(
            name=name,
            contact_type=ContactType.ORGANIZATION,
            email=email,
            is_active=True,
        )

    def test_planned_status_notifications_use_frozen_party_snapshot_emails(self):
        shipper = self._create_org(
            "Association Snapshot",
            email="shipper-old@example.com",
        )
        recipient = self._create_org(
            "Hopital Snapshot",
            email="recipient-old@example.com",
        )
        snapshot = build_shipment_party_snapshot(
            shipper_contact=shipper,
            recipient_contact=recipient,
            correspondent_contact=None,
            shipper_name=shipper.name,
            recipient_name=recipient.name,
        )
        shipment = Shipment.objects.create(
            status=ShipmentStatus.DRAFT,
            shipper_name=shipper.name,
            shipper_contact_ref=shipper,
            recipient_name=recipient.name,
            recipient_contact_ref=recipient,
            destination_address="1 Rue du Test",
            destination_country="France",
            party_snapshot=snapshot,
            created_by=self.creator,
        )

        shipper.email = "shipper-new@example.com"
        shipper.save(update_fields=["email"])
        recipient.email = "recipient-new@example.com"
        recipient.save(update_fields=["email"])

        with self.captureOnCommitCallbacks(execute=True):
            shipment.status = ShipmentStatus.PLANNED
            shipment.save(update_fields=["status"])

        events = list(
            IntegrationEvent.objects.filter(
                direction=IntegrationDirection.OUTBOUND,
                source="wms.email",
                event_type="send_email",
                status=IntegrationStatus.PENDING,
            )
        )

        recipients = {tuple(event.payload.get("recipient", [])) for event in events}
        self.assertIn(("shipper-old@example.com",), recipients)
        self.assertIn(("recipient-old@example.com",), recipients)
        self.assertNotIn(("shipper-new@example.com",), recipients)
        self.assertNotIn(("recipient-new@example.com",), recipients)

    def test_boarding_ok_notifications_use_frozen_correspondent_snapshot_email(self):
        original_correspondent = self._create_org(
            "ASF - CORRESPONDANT Bamako",
            email="correspondent-old@example.com",
        )
        destination = Destination.objects.create(
            city="Bamako",
            iata_code="BKO",
            country="Mali",
            correspondent_contact=original_correspondent,
            is_active=True,
        )
        snapshot = build_shipment_party_snapshot(
            shipper_contact=None,
            recipient_contact=None,
            correspondent_contact=original_correspondent,
            correspondent_name=original_correspondent.name,
        )
        shipment = Shipment.objects.create(
            status=ShipmentStatus.PLANNED,
            shipper_name="Association A",
            recipient_name="Hopital B",
            correspondent_name=original_correspondent.name,
            destination=destination,
            destination_address="Aeroport de Bamako",
            destination_country="Mali",
            party_snapshot=snapshot,
            created_by=self.creator,
        )

        replacement_correspondent = self._create_org(
            "ASF - CORRESPONDANT Nouveau",
            email="correspondent-new@example.com",
        )
        destination.correspondent_contact = replacement_correspondent
        destination.save(update_fields=["correspondent_contact"])

        with self.captureOnCommitCallbacks(execute=True):
            ShipmentTrackingEvent.objects.create(
                shipment=shipment,
                status=ShipmentTrackingStatus.BOARDING_OK,
                actor_name="Boarding Agent",
                actor_structure="ASF",
                comments="ok",
            )

        events = list(
            IntegrationEvent.objects.filter(
                direction=IntegrationDirection.OUTBOUND,
                source="wms.email",
                event_type="send_email",
                status=IntegrationStatus.PENDING,
            )
        )

        recipients = {tuple(event.payload.get("recipient", [])) for event in events}
        self.assertIn(("correspondent-old@example.com",), recipients)
        self.assertNotIn(("correspondent-new@example.com",), recipients)
