from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase

from contacts.models import Contact, ContactType
from wms.models import (
    Destination,
    DestinationCorrespondentDefault,
    DestinationCorrespondentOverride,
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
from wms.signals import _notify_shipment_status_change, _notify_tracking_event


class SignalsOrgRoleNotificationsTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="signals-org-role-user",
            email="signals-org-role-user@example.org",
            password="pass1234",
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

    def _create_shipment(self, *, shipper: Contact, recipient: Contact, destination: Destination):
        shipment = Shipment.objects.create(
            status=ShipmentStatus.DRAFT,
            shipper_name=shipper.name,
            shipper_contact_ref=shipper,
            recipient_name=recipient.name,
            recipient_contact_ref=recipient,
            correspondent_name="",
            destination=destination,
            destination_address=str(destination),
            destination_country=destination.country,
            created_by=self.user,
        )
        shipment._previous_status = ShipmentStatus.DRAFT
        return shipment

    def test_status_notification_uses_policy_with_primary_fallback(self):
        shipper = self._create_org("Shipper A", "shipper-a@example.org")
        recipient = self._create_org("Recipient A", "recipient-a@example.org")
        correspondent = self._create_org("Correspondent A", "corr-a@example.org")
        destination = Destination.objects.create(
            city="Bamako",
            iata_code="BKO-S1",
            country="Mali",
            correspondent_contact=correspondent,
            is_active=True,
        )
        self._create_role_assignment_with_primary(
            organization=shipper,
            role=OrganizationRole.SHIPPER,
            primary_email="shipper-primary@example.org",
        )
        self._create_role_assignment_with_primary(
            organization=recipient,
            role=OrganizationRole.RECIPIENT,
            primary_email="recipient-primary@example.org",
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
            is_notifiable=False,
            is_active=True,
        )

        shipment = self._create_shipment(
            shipper=shipper,
            recipient=recipient,
            destination=destination,
        )
        shipment.status = ShipmentStatus.SHIPPED

        with (
            mock.patch("wms.signals._shipment_status_admin_recipients", return_value=[]),
            mock.patch("wms.signals.send_or_enqueue_email_safe") as send_mock,
            mock.patch(
                "wms.signals.transaction.on_commit", side_effect=lambda callback: callback()
            ),
        ):
            _notify_shipment_status_change(None, shipment, created=False)

        self.assertEqual(send_mock.call_count, 2)
        recipients = {tuple(call.kwargs["recipient"]) for call in send_mock.call_args_list}
        self.assertSetEqual(
            recipients,
            {
                ("shipper-a@example.org",),
                ("recipient-a@example.org",),
            },
        )

    def test_status_notification_deduplicates_same_email_across_roles(self):
        shipper = self._create_org("Shipper B", "shared@example.org")
        recipient = self._create_org("Recipient B", "shared@example.org")
        correspondent = self._create_org("Correspondent B", "corr-b@example.org")
        destination = Destination.objects.create(
            city="Douala",
            iata_code="DLA-S2",
            country="Cameroun",
            correspondent_contact=correspondent,
            is_active=True,
        )

        self._create_role_assignment_with_primary(
            organization=shipper,
            role=OrganizationRole.SHIPPER,
            primary_email="shared@example.org",
        )
        self._create_role_assignment_with_primary(
            organization=recipient,
            role=OrganizationRole.RECIPIENT,
            primary_email="shared@example.org",
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

        shipment = self._create_shipment(
            shipper=shipper,
            recipient=recipient,
            destination=destination,
        )
        shipment.status = ShipmentStatus.SHIPPED

        with (
            mock.patch("wms.signals._shipment_status_admin_recipients", return_value=[]),
            mock.patch("wms.signals.send_or_enqueue_email_safe") as send_mock,
            mock.patch(
                "wms.signals.transaction.on_commit", side_effect=lambda callback: callback()
            ),
        ):
            _notify_shipment_status_change(None, shipment, created=False)

        self.assertEqual(send_mock.call_count, 1)
        self.assertEqual(send_mock.call_args.kwargs["recipient"], ["shared@example.org"])

    def test_status_notification_adds_coordination_message_for_correspondents(self):
        shipper = self._create_org("Shipper C", "shipper-c@example.org")
        recipient = self._create_org("Recipient C", "recipient-c@example.org")
        corr_default = self._create_org("Corr Default", "corr-default@example.org")
        corr_dedicated = self._create_org("Corr Dedicated", "corr-dedicated@example.org")
        destination = Destination.objects.create(
            city="Ndjamena",
            iata_code="NDJ-S3",
            country="Tchad",
            correspondent_contact=corr_default,
            is_active=True,
        )

        self._create_role_assignment_with_primary(
            organization=corr_default,
            role=OrganizationRole.CORRESPONDENT,
            primary_email="corr-default@example.org",
        )
        self._create_role_assignment_with_primary(
            organization=corr_dedicated,
            role=OrganizationRole.CORRESPONDENT,
            primary_email="corr-dedicated@example.org",
        )

        DestinationCorrespondentDefault.objects.create(
            destination=destination,
            correspondent_org=corr_default,
            is_active=True,
        )
        DestinationCorrespondentOverride.objects.create(
            destination=destination,
            correspondent_org=corr_dedicated,
            shipper_org=shipper,
            is_active=True,
        )

        RoleEventPolicy.objects.create(
            role=OrganizationRole.CORRESPONDENT,
            event_type=RoleEventType.SHIPMENT_STATUS_UPDATED,
            is_notifiable=True,
            is_active=True,
        )

        shipment = self._create_shipment(
            shipper=shipper,
            recipient=recipient,
            destination=destination,
        )
        shipment.status = ShipmentStatus.PLANNED

        with (
            mock.patch("wms.signals._shipment_status_admin_recipients", return_value=[]),
            mock.patch("wms.signals.send_or_enqueue_email_safe") as send_mock,
            mock.patch(
                "wms.signals.transaction.on_commit", side_effect=lambda callback: callback()
            ),
        ):
            _notify_shipment_status_change(None, shipment, created=False)

        recipients = {call.kwargs["recipient"][0] for call in send_mock.call_args_list}
        self.assertSetEqual(
            recipients,
            {
                "shipper-c@example.org",
                "recipient-c@example.org",
                "corr-default@example.org",
            },
        )
        self.assertNotIn("corr-dedicated@example.org", recipients)

    def test_tracking_event_uses_tracking_policy(self):
        shipper = self._create_org("Shipper D", "shipper-d@example.org")
        recipient = self._create_org("Recipient D", "recipient-d@example.org")
        correspondent = self._create_org("Correspondent D", "corr-d@example.org")
        destination = Destination.objects.create(
            city="Niamey",
            iata_code="NIM-S4",
            country="Niger",
            correspondent_contact=correspondent,
            is_active=True,
        )

        self._create_role_assignment_with_primary(
            organization=shipper,
            role=OrganizationRole.SHIPPER,
            primary_email="shipper-tracking@example.org",
        )
        RoleEventPolicy.objects.create(
            role=OrganizationRole.SHIPPER,
            event_type=RoleEventType.SHIPMENT_TRACKING_UPDATED,
            is_notifiable=True,
            is_active=True,
        )

        shipment = self._create_shipment(
            shipper=shipper,
            recipient=recipient,
            destination=destination,
        )
        tracking_event = ShipmentTrackingEvent.objects.create(
            shipment=shipment,
            status=ShipmentTrackingStatus.BOARDING_OK,
            actor_name="Agent",
            actor_structure="ASF",
            comments="ok",
        )

        with (
            mock.patch("wms.signals.get_admin_emails", return_value=[]),
            mock.patch("wms.signals.send_or_enqueue_email_safe") as send_mock,
            mock.patch(
                "wms.signals.transaction.on_commit", side_effect=lambda callback: callback()
            ),
        ):
            _notify_tracking_event(None, tracking_event, created=True)

        self.assertEqual(send_mock.call_count, 1)
        self.assertEqual(send_mock.call_args.kwargs["recipient"], ["corr-d@example.org"])
