from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase

from contacts.models import Contact, ContactType
from wms.models import (
    ContactSubscription,
    Destination,
    DestinationCorrespondentDefault,
    IntegrationDirection,
    IntegrationEvent,
    IntegrationStatus,
    NotificationChannel,
    OrganizationContact,
    OrganizationRole,
    OrganizationRoleAssignment,
    OrganizationRoleContact,
    RoleEventPolicy,
    RoleEventType,
    Shipment,
    ShipmentStatus,
    ShipmentTrackingEvent,
    ShipmentTrackingStatus,
)


class ShipmentSignalEmailQueueTests(TestCase):
    def setUp(self):
        self.send_email_patcher = mock.patch(
            "wms.emailing.send_email_safe",
            return_value=False,
        )
        self.send_email_patcher.start()
        self.addCleanup(self.send_email_patcher.stop)

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

    def _create_org(self, name: str, email: str) -> Contact:
        return Contact.objects.create(
            name=name,
            email=email,
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )

    def _create_role_assignment_with_primary(
        self,
        *,
        organization: Contact,
        role: str,
        primary_email: str,
    ) -> OrganizationRoleAssignment:
        assignment = OrganizationRoleAssignment.objects.create(
            organization=organization,
            role=role,
            is_active=True,
        )
        org_contact = OrganizationContact.objects.create(
            organization=organization,
            first_name=role,
            last_name="Primary",
            email=primary_email,
            is_active=True,
        )
        OrganizationRoleContact.objects.create(
            role_assignment=assignment,
            contact=org_contact,
            is_primary=True,
            is_active=True,
        )
        return assignment

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

    def test_delivered_status_queues_role_based_delivery_notifications(self):
        association_contact = self._create_org(
            "Association Notify Deliveries",
            "assoc-delivery@example.com",
        )
        recipient_contact = self._create_org(
            "Recipient Notify Deliveries",
            "recipient-delivery@example.com",
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
        shipper_assignment = self._create_role_assignment_with_primary(
            organization=association_contact,
            role=OrganizationRole.SHIPPER,
            primary_email="assoc-delivery@example.com",
        )
        recipient_assignment = self._create_role_assignment_with_primary(
            organization=recipient_contact,
            role=OrganizationRole.RECIPIENT,
            primary_email="delivery@example.com",
        )
        recipient_contact_two = OrganizationContact.objects.create(
            organization=recipient_contact,
            first_name="Delivery",
            last_name="Secondary",
            email="second@example.com",
            is_active=True,
        )
        recipient_role_contact_two = OrganizationRoleContact.objects.create(
            role_assignment=recipient_assignment,
            contact=recipient_contact_two,
            is_primary=False,
            is_active=True,
        )
        RoleEventPolicy.objects.create(
            role=OrganizationRole.SHIPPER,
            event_type=RoleEventType.SHIPMENT_STATUS_UPDATED,
            is_notifiable=True,
            is_active=True,
        )
        RoleEventPolicy.objects.create(
            role=OrganizationRole.RECIPIENT,
            event_type=RoleEventType.SHIPMENT_DELIVERED,
            is_notifiable=True,
            is_active=True,
        )
        recipient_primary_role_contact = recipient_assignment.role_contacts.get(is_primary=True)
        ContactSubscription.objects.create(
            role_contact=recipient_primary_role_contact,
            event_type=RoleEventType.SHIPMENT_DELIVERED,
            channel=NotificationChannel.EMAIL,
            destination=destination,
            shipper_org=association_contact,
            is_active=True,
        )
        ContactSubscription.objects.create(
            role_contact=recipient_role_contact_two,
            event_type=RoleEventType.SHIPMENT_DELIVERED,
            channel=NotificationChannel.EMAIL,
            destination=destination,
            shipper_org=association_contact,
            is_active=True,
        )
        self.shipment.shipper_contact_ref = association_contact
        self.shipment.recipient_contact_ref = recipient_contact
        self.shipment.destination = destination
        self.shipment.save(
            update_fields=["shipper_contact_ref", "recipient_contact_ref", "destination"]
        )

        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            self.shipment.status = ShipmentStatus.DELIVERED
            self.shipment.save(update_fields=["status"])

        self.assertEqual(len(callbacks), 3)
        events = list(
            IntegrationEvent.objects.filter(
                direction=IntegrationDirection.OUTBOUND,
                source="wms.email",
                event_type="send_email",
                status=IntegrationStatus.PENDING,
            )
        )
        self.assertEqual(len(events), 3)
        delivery_subject = f"ASF WMS - Expedition {self.shipment.reference} : livraison confirmee"
        delivery_event = next(
            event for event in events if event.payload.get("subject") == delivery_subject
        )
        self.assertEqual(
            delivery_event.payload.get("recipient"),
            ["delivery@example.com", "second@example.com"],
        )
        status_subject = f"ASF WMS - Expédition {self.shipment.reference} : statut Livré"
        status_event = next(
            event
            for event in events
            if event.payload.get("subject") == status_subject
            and event.payload.get("recipient") == ["assoc-delivery@example.com"]
        )
        self.assertIsNotNone(status_event)

    def test_shipment_status_change_includes_shipment_status_update_group(self):
        grouped_staff = get_user_model().objects.create_user(
            username="shipment-status-grouped",
            email="shipment-status-grouped@example.com",
            password="pass1234",
            is_staff=True,
        )
        Group.objects.get_or_create(name="Shipment_Status_Update")[0].user_set.add(grouped_staff)

        with self.captureOnCommitCallbacks(execute=True):
            self.shipment.status = ShipmentStatus.SHIPPED
            self.shipment.save(update_fields=["status"])

        event = IntegrationEvent.objects.filter(
            direction=IntegrationDirection.OUTBOUND,
            source="wms.email",
            event_type="send_email",
            status=IntegrationStatus.PENDING,
            payload__subject=f"ASF WMS - Expédition {self.shipment.reference} : statut mis à jour",
        ).first()
        self.assertIsNotNone(event)
        self.assertEqual(
            set(event.payload.get("recipient", [])),
            {"admin@example.com", "shipment-status-grouped@example.com"},
        )

    def test_planned_status_change_notifies_shipper_and_recipient(self):
        shipper = self._create_org("Shipper", "shipper@example.com")
        recipient = self._create_org("Recipient", "recipient@example.com")
        self._create_role_assignment_with_primary(
            organization=shipper,
            role=OrganizationRole.SHIPPER,
            primary_email="shipper@example.com",
        )
        self._create_role_assignment_with_primary(
            organization=recipient,
            role=OrganizationRole.RECIPIENT,
            primary_email="recipient@example.com",
        )
        RoleEventPolicy.objects.create(
            role=OrganizationRole.SHIPPER,
            event_type=RoleEventType.SHIPMENT_STATUS_UPDATED,
            is_notifiable=True,
            is_active=True,
        )
        RoleEventPolicy.objects.create(
            role=OrganizationRole.RECIPIENT,
            event_type=RoleEventType.SHIPMENT_STATUS_UPDATED,
            is_notifiable=True,
            is_active=True,
        )
        self.shipment.shipper_contact_ref = shipper
        self.shipment.recipient_contact_ref = recipient
        self.shipment.save(update_fields=["shipper_contact_ref", "recipient_contact_ref"])

        with self.captureOnCommitCallbacks(execute=True):
            self.shipment.status = ShipmentStatus.PLANNED
            self.shipment.save(update_fields=["status"])

        events = list(
            IntegrationEvent.objects.filter(
                direction=IntegrationDirection.OUTBOUND,
                source="wms.email",
                event_type="send_email",
                status=IntegrationStatus.PENDING,
                payload__subject=f"ASF WMS - Expédition {self.shipment.reference} : statut Planifié",
            )
        )
        self.assertEqual(len(events), 2)
        self.assertEqual(
            {tuple(event.payload.get("recipient", [])) for event in events},
            {("shipper@example.com",), ("recipient@example.com",)},
        )

    def test_planned_status_change_notifies_role_based_correspondents(self):
        correspondent = self._create_org("Correspondent", "correspondent@example.com")
        destination = Destination.objects.create(
            city="Bamako",
            iata_code="BKO-Q",
            country="Mali",
            correspondent_contact=correspondent,
            is_active=True,
        )
        self._create_role_assignment_with_primary(
            organization=correspondent,
            role=OrganizationRole.CORRESPONDENT,
            primary_email="correspondent@example.com",
        )
        RoleEventPolicy.objects.create(
            role=OrganizationRole.CORRESPONDENT,
            event_type=RoleEventType.SHIPMENT_STATUS_UPDATED,
            is_notifiable=True,
            is_active=True,
        )
        DestinationCorrespondentDefault.objects.create(
            destination=destination,
            correspondent_org=correspondent,
            is_active=True,
        )
        self.shipment.destination = destination
        self.shipment.save(update_fields=["destination"])

        with self.captureOnCommitCallbacks(execute=True):
            self.shipment.status = ShipmentStatus.PLANNED
            self.shipment.save(update_fields=["status"])

        event = IntegrationEvent.objects.filter(
            direction=IntegrationDirection.OUTBOUND,
            source="wms.email",
            event_type="send_email",
            status=IntegrationStatus.PENDING,
            payload__subject=f"ASF WMS - Expédition {self.shipment.reference} : statut Planifié",
        ).first()
        self.assertIsNotNone(event)
        self.assertEqual(
            event.payload.get("recipient"),
            ["correspondent@example.com"],
        )

    def test_boarding_ok_tracking_event_notifies_role_based_correspondents(self):
        correspondent = self._create_org(
            "Correspondent Boarding",
            "correspondent-boarding@example.com",
        )
        destination = Destination.objects.create(
            city="Dakar",
            iata_code="DKR-Q",
            country="Senegal",
            correspondent_contact=correspondent,
            is_active=True,
        )
        self._create_role_assignment_with_primary(
            organization=correspondent,
            role=OrganizationRole.CORRESPONDENT,
            primary_email="correspondent-boarding@example.com",
        )
        RoleEventPolicy.objects.create(
            role=OrganizationRole.CORRESPONDENT,
            event_type=RoleEventType.SHIPMENT_TRACKING_UPDATED,
            is_notifiable=True,
            is_active=True,
        )
        DestinationCorrespondentDefault.objects.create(
            destination=destination,
            correspondent_org=correspondent,
            is_active=True,
        )
        self.shipment.destination = destination
        self.shipment.status = ShipmentStatus.PLANNED
        self.shipment.save(update_fields=["destination", "status"])

        with self.captureOnCommitCallbacks(execute=True):
            ShipmentTrackingEvent.objects.create(
                shipment=self.shipment,
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
                payload__subject=f"ASF WMS - Suivi expédition {self.shipment.reference}",
            )
        )
        self.assertEqual(len(events), 2)
        event = next(
            (
                candidate
                for candidate in events
                if candidate.payload.get("recipient") == ["correspondent-boarding@example.com"]
            ),
            None,
        )
        self.assertIsNotNone(event)
        self.assertEqual(
            event.payload.get("recipient"),
            ["correspondent-boarding@example.com"],
        )
