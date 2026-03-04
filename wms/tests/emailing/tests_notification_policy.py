from django.test import TestCase

from contacts.models import Contact, ContactType
from wms.models import (
    ContactSubscription,
    Destination,
    OrganizationContact,
    OrganizationRole,
    OrganizationRoleAssignment,
    OrganizationRoleContact,
    RoleEventPolicy,
    RoleEventType,
)
from wms.notification_policy import resolve_notification_recipients


class NotificationPolicyTests(TestCase):
    def _create_org(self, name: str, *, email: str = "") -> Contact:
        return Contact.objects.create(
            name=name,
            email=email,
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )

    def _create_destination(self, iata: str) -> Destination:
        correspondent = self._create_org(f"Corr {iata}")
        return Destination.objects.create(
            city=f"City {iata}",
            iata_code=iata,
            country="Country",
            correspondent_contact=correspondent,
            is_active=True,
        )

    def _create_role_assignment(self, organization: Contact) -> OrganizationRoleAssignment:
        return OrganizationRoleAssignment.objects.create(
            organization=organization,
            role=OrganizationRole.SHIPPER,
            is_active=False,
        )

    def _create_role_contact(
        self,
        *,
        assignment: OrganizationRoleAssignment,
        email: str,
        first_name: str,
        is_primary: bool,
    ) -> OrganizationRoleContact:
        contact = OrganizationContact.objects.create(
            organization=assignment.organization,
            first_name=first_name,
            last_name="User",
            email=email,
            is_active=True,
        )
        return OrganizationRoleContact.objects.create(
            role_assignment=assignment,
            contact=contact,
            is_primary=is_primary,
            is_active=True,
        )

    def _enable_policy(self, *, role: str, event_type: str) -> RoleEventPolicy:
        return RoleEventPolicy.objects.create(
            role=role,
            event_type=event_type,
            is_visible=True,
            is_notifiable=True,
            is_active=True,
        )

    def test_notify_uses_fallback_primary_when_no_subscription(self):
        shipper = self._create_org("Shipper Notify")
        assignment = self._create_role_assignment(shipper)
        self._create_role_contact(
            assignment=assignment,
            email="primary@example.org",
            first_name="Primary",
            is_primary=True,
        )
        self._enable_policy(
            role=OrganizationRole.SHIPPER,
            event_type=RoleEventType.SHIPMENT_DELIVERED,
        )

        recipients = resolve_notification_recipients(
            role_assignment=assignment,
            event_type=RoleEventType.SHIPMENT_DELIVERED,
        )
        self.assertEqual(recipients, ["primary@example.org"])

    def test_subscription_filters_use_and_semantics(self):
        shipper = self._create_org("Shipper Filters")
        recipient_ok = self._create_org("Recipient OK")
        recipient_other = self._create_org("Recipient Other")
        destination_ok = self._create_destination("FLT")
        destination_other = self._create_destination("FL2")
        assignment = self._create_role_assignment(shipper)
        primary = self._create_role_contact(
            assignment=assignment,
            email="primary-filters@example.org",
            first_name="Primary",
            is_primary=True,
        )
        target = self._create_role_contact(
            assignment=assignment,
            email="ops@example.org",
            first_name="Ops",
            is_primary=False,
        )
        self._enable_policy(
            role=OrganizationRole.SHIPPER,
            event_type=RoleEventType.SHIPMENT_DELIVERED,
        )
        ContactSubscription.objects.create(
            role_contact=target,
            event_type=RoleEventType.SHIPMENT_DELIVERED,
            channel="email",
            destination=destination_ok,
            recipient_org=recipient_ok,
            is_active=True,
        )

        recipients_match = resolve_notification_recipients(
            role_assignment=assignment,
            event_type=RoleEventType.SHIPMENT_DELIVERED,
            destination=destination_ok,
            recipient_org=recipient_ok,
        )
        self.assertEqual(recipients_match, ["ops@example.org"])

        recipients_miss = resolve_notification_recipients(
            role_assignment=assignment,
            event_type=RoleEventType.SHIPMENT_DELIVERED,
            destination=destination_other,
            recipient_org=recipient_ok,
        )
        self.assertEqual(recipients_miss, [primary.contact.email])

        recipients_miss_second = resolve_notification_recipients(
            role_assignment=assignment,
            event_type=RoleEventType.SHIPMENT_DELIVERED,
            destination=destination_ok,
            recipient_org=recipient_other,
        )
        self.assertEqual(recipients_miss_second, [primary.contact.email])

    def test_notification_recipient_resolution_deduplicates_emails(self):
        shipper = self._create_org("Shipper Dedup")
        assignment = self._create_role_assignment(shipper)
        primary = self._create_role_contact(
            assignment=assignment,
            email="notify@example.org",
            first_name="Primary",
            is_primary=True,
        )
        second = self._create_role_contact(
            assignment=assignment,
            email="Notify@example.org",
            first_name="Second",
            is_primary=False,
        )
        self._enable_policy(
            role=OrganizationRole.SHIPPER,
            event_type=RoleEventType.SHIPMENT_DELIVERED,
        )
        ContactSubscription.objects.create(
            role_contact=primary,
            event_type=RoleEventType.SHIPMENT_DELIVERED,
            channel="email",
            is_active=True,
        )
        ContactSubscription.objects.create(
            role_contact=second,
            event_type=RoleEventType.SHIPMENT_DELIVERED,
            channel="email",
            is_active=True,
        )

        recipients = resolve_notification_recipients(
            role_assignment=assignment,
            event_type=RoleEventType.SHIPMENT_DELIVERED,
        )
        self.assertEqual(recipients, ["notify@example.org"])

    def test_notification_resolution_respects_role_event_policy(self):
        shipper = self._create_org("Shipper Policy")
        assignment = self._create_role_assignment(shipper)
        role_contact = self._create_role_contact(
            assignment=assignment,
            email="policy@example.org",
            first_name="Policy",
            is_primary=True,
        )
        RoleEventPolicy.objects.create(
            role=OrganizationRole.SHIPPER,
            event_type=RoleEventType.SHIPMENT_DELIVERED,
            is_visible=True,
            is_notifiable=False,
            is_active=True,
        )
        ContactSubscription.objects.create(
            role_contact=role_contact,
            event_type=RoleEventType.SHIPMENT_DELIVERED,
            channel="email",
            is_active=True,
        )

        recipients = resolve_notification_recipients(
            role_assignment=assignment,
            event_type=RoleEventType.SHIPMENT_DELIVERED,
        )
        self.assertEqual(recipients, [])
