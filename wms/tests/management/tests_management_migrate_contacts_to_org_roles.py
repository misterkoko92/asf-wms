from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from contacts.models import Contact, ContactTag, ContactType
from wms.models import (
    Destination,
    MigrationReviewItem,
    OrganizationRole,
    OrganizationRoleAssignment,
    RecipientBinding,
    ShipperScope,
)
from wms.organization_roles_backfill import (
    REVIEW_REASON_MISSING_DESTINATION,
    REVIEW_REASON_MISSING_SHIPPER_LINKS,
)


class MigrateContactsToOrgRolesCommandTests(TestCase):
    def _create_org(self, name: str) -> Contact:
        return Contact.objects.create(
            name=name,
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )

    def _tag_contact(self, contact: Contact, tag_name: str):
        tag, _ = ContactTag.objects.get_or_create(name=tag_name)
        contact.tags.add(tag)

    def _create_destination(self, iata: str) -> Destination:
        correspondent = self._create_org(f"Correspondent {iata}")
        return Destination.objects.create(
            city=f"City {iata}",
            iata_code=iata,
            country="Country",
            correspondent_contact=correspondent,
            is_active=True,
        )

    def test_backfill_maps_legacy_recipient_links_without_global_binding(self):
        destination = self._create_destination("BKO")
        shipper = self._create_org("Shipper BKO")
        self._tag_contact(shipper, "expediteur")
        shipper.destinations.add(destination)

        recipient = self._create_org("Recipient BKO")
        self._tag_contact(recipient, "destinataire")
        recipient.destinations.add(destination)
        recipient.linked_shippers.add(shipper)

        call_command("migrate_contacts_to_org_roles", stdout=StringIO())

        shipper_assignment = OrganizationRoleAssignment.objects.get(
            organization=shipper,
            role=OrganizationRole.SHIPPER,
        )
        recipient_assignment = OrganizationRoleAssignment.objects.get(
            organization=recipient,
            role=OrganizationRole.RECIPIENT,
        )
        self.assertTrue(shipper_assignment.is_active)
        self.assertTrue(recipient_assignment.is_active)
        self.assertTrue(
            ShipperScope.objects.filter(
                role_assignment=shipper_assignment,
                destination=destination,
                all_destinations=False,
                is_active=True,
            ).exists()
        )
        self.assertTrue(
            RecipientBinding.objects.filter(
                shipper_org=shipper,
                recipient_org=recipient,
                destination=destination,
                is_active=True,
            ).exists()
        )
        self.assertEqual(MigrationReviewItem.objects.count(), 0)

    def test_backfill_routes_ambiguous_recipient_without_shipper_links_to_review_queue(self):
        destination = self._create_destination("DLA")
        recipient = self._create_org("Recipient Ambiguous")
        self._tag_contact(recipient, "destinataire")
        recipient.destinations.add(destination)

        call_command("migrate_contacts_to_org_roles", stdout=StringIO())

        self.assertFalse(
            RecipientBinding.objects.filter(recipient_org=recipient).exists()
        )
        self.assertTrue(
            MigrationReviewItem.objects.filter(
                organization=recipient,
                role=OrganizationRole.RECIPIENT,
                reason_code=REVIEW_REASON_MISSING_SHIPPER_LINKS,
                status="open",
            ).exists()
        )

    def test_backfill_routes_recipient_without_destination_to_review_queue(self):
        shipper = self._create_org("Shipper No Destination")
        self._tag_contact(shipper, "expediteur")

        recipient = self._create_org("Recipient No Destination")
        self._tag_contact(recipient, "destinataire")
        recipient.linked_shippers.add(shipper)

        call_command("migrate_contacts_to_org_roles", stdout=StringIO())

        self.assertFalse(
            RecipientBinding.objects.filter(recipient_org=recipient).exists()
        )
        self.assertTrue(
            MigrationReviewItem.objects.filter(
                organization=recipient,
                role=OrganizationRole.RECIPIENT,
                reason_code=REVIEW_REASON_MISSING_DESTINATION,
                status="open",
            ).exists()
        )
