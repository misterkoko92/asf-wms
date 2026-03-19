from django.test import TestCase

from contacts.models import Contact, ContactType
from wms.default_shipper_bindings import suppress_default_shipper_binding_sync
from wms.models import (
    Destination,
    OrganizationRole,
    OrganizationRoleAssignment,
    RecipientBinding,
)


class CorrespondentRecipientPromotionTests(TestCase):
    def test_ensure_destination_correspondent_recipient_ready_skips_asf_bindings_when_sync_suppressed(
        self,
    ):
        from contacts.correspondent_recipient_promotion import (
            SUPPORT_ORGANIZATION_NAME,
            ensure_destination_correspondent_recipient_ready,
        )

        default_shipper = Contact.objects.create(
            name="AVIATION SANS FRONTIERES",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        OrganizationRoleAssignment.objects.create(
            organization=default_shipper,
            role=OrganizationRole.SHIPPER,
            is_active=True,
        )
        correspondent = Contact.objects.create(
            name="Suppressed Correspondent",
            contact_type=ContactType.PERSON,
            is_active=True,
        )
        destination = Destination.objects.create(
            city="Dakar",
            iata_code="DKR",
            country="Senegal",
            correspondent_contact=correspondent,
            is_active=True,
        )

        with suppress_default_shipper_binding_sync():
            ensure_destination_correspondent_recipient_ready(destination)

        correspondent.refresh_from_db()
        support_organization = Contact.objects.get(
            name=SUPPORT_ORGANIZATION_NAME,
            contact_type=ContactType.ORGANIZATION,
        )
        self.assertEqual(correspondent.organization, support_organization)
        self.assertTrue(
            OrganizationRoleAssignment.objects.filter(
                organization=support_organization,
                role=OrganizationRole.RECIPIENT,
                is_active=True,
            ).exists()
        )
        self.assertFalse(
            RecipientBinding.objects.filter(
                shipper_org=default_shipper,
                recipient_org=support_organization,
                destination=destination,
                is_active=True,
            ).exists()
        )

    def test_promote_correspondent_org_creates_recipient_role_from_destination_assignment(self):
        from contacts.correspondent_recipient_promotion import (
            promote_correspondent_to_recipient_ready,
        )

        organization = Contact.objects.create(
            name="Correspondent Org",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        Destination.objects.create(
            city="Douala",
            iata_code="DLA",
            country="Cameroun",
            correspondent_contact=organization,
            is_active=True,
        )

        promote_correspondent_to_recipient_ready(organization)

        self.assertTrue(
            OrganizationRoleAssignment.objects.filter(
                organization=organization,
                role=OrganizationRole.RECIPIENT,
                is_active=True,
            ).exists()
        )

    def test_promote_person_without_org_scopes_contact_from_destination_reference(self):
        from contacts.correspondent_recipient_promotion import (
            SUPPORT_ORGANIZATION_NAME,
            promote_correspondent_to_recipient_ready,
        )

        person = Contact.objects.create(
            name="Scoped Correspondent",
            contact_type=ContactType.PERSON,
            is_active=True,
        )
        destination = Destination.objects.create(
            city="Antananarivo",
            iata_code="TNR",
            country="Madagascar",
            correspondent_contact=person,
            is_active=True,
        )

        promote_correspondent_to_recipient_ready(person)

        person.refresh_from_db()
        support_organization = Contact.objects.get(
            name=SUPPORT_ORGANIZATION_NAME,
            contact_type=ContactType.ORGANIZATION,
        )
        self.assertEqual(person.organization, support_organization)
        self.assertTrue(
            OrganizationRoleAssignment.objects.filter(
                organization=support_organization,
                role=OrganizationRole.RECIPIENT,
                is_active=True,
            ).exists()
        )

    def test_promote_person_with_org_reuses_existing_org(self):
        from contacts.correspondent_recipient_promotion import (
            SUPPORT_ORGANIZATION_NAME,
            promote_correspondent_to_recipient_ready,
        )

        organization = Contact.objects.create(
            name="Recipient Org",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        person = Contact.objects.create(
            name="Person Correspondent",
            contact_type=ContactType.PERSON,
            organization=organization,
            is_active=True,
        )
        Destination.objects.create(
            city="Bamako",
            iata_code="BKO",
            country="Mali",
            correspondent_contact=person,
            is_active=True,
        )

        promote_correspondent_to_recipient_ready(person)

        person.refresh_from_db()
        self.assertEqual(person.organization, organization)
        self.assertFalse(
            Contact.objects.filter(
                name=SUPPORT_ORGANIZATION_NAME,
                contact_type=ContactType.ORGANIZATION,
            ).exists()
        )
        self.assertTrue(
            OrganizationRoleAssignment.objects.filter(
                organization=organization,
                role=OrganizationRole.RECIPIENT,
                is_active=True,
            ).exists()
        )

    def test_promote_person_without_org_creates_shared_support_org(self):
        from contacts.correspondent_recipient_promotion import (
            SUPPORT_ORGANIZATION_NAME,
            promote_correspondent_to_recipient_ready,
        )

        person = Contact.objects.create(
            name="Standalone Correspondent",
            contact_type=ContactType.PERSON,
            is_active=True,
        )
        Destination.objects.create(
            city="Bangui",
            iata_code="BGF",
            country="RCA",
            correspondent_contact=person,
            is_active=True,
        )

        promote_correspondent_to_recipient_ready(person)

        person.refresh_from_db()
        support_organization = Contact.objects.get(
            name=SUPPORT_ORGANIZATION_NAME,
            contact_type=ContactType.ORGANIZATION,
        )
        self.assertEqual(person.organization, support_organization)
        self.assertTrue(
            OrganizationRoleAssignment.objects.filter(
                organization=support_organization,
                role=OrganizationRole.RECIPIENT,
                is_active=True,
            ).exists()
        )

    def test_promote_person_without_org_reuses_existing_support_org(self):
        from contacts.correspondent_recipient_promotion import (
            SUPPORT_ORGANIZATION_NAME,
            promote_correspondent_to_recipient_ready,
        )

        existing_support_org = Contact.objects.create(
            name=SUPPORT_ORGANIZATION_NAME,
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        first = Contact.objects.create(
            name="First Correspondent",
            contact_type=ContactType.PERSON,
            is_active=True,
        )
        second = Contact.objects.create(
            name="Second Correspondent",
            contact_type=ContactType.PERSON,
            is_active=True,
        )
        Destination.objects.create(
            city="Lome",
            iata_code="LFW",
            country="Togo",
            correspondent_contact=first,
            is_active=True,
        )
        Destination.objects.create(
            city="Ndjamena",
            iata_code="NDJ",
            country="Tchad",
            correspondent_contact=second,
            is_active=True,
        )

        promote_correspondent_to_recipient_ready(first)
        promote_correspondent_to_recipient_ready(second)

        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(first.organization, existing_support_org)
        self.assertEqual(second.organization, existing_support_org)
        self.assertEqual(
            Contact.objects.filter(
                name=SUPPORT_ORGANIZATION_NAME,
                contact_type=ContactType.ORGANIZATION,
            ).count(),
            1,
        )

    def test_promotion_skips_contacts_without_active_destination_assignment(self):
        from contacts.correspondent_recipient_promotion import (
            SUPPORT_ORGANIZATION_NAME,
            promote_correspondent_to_recipient_ready,
        )

        person = Contact.objects.create(
            name="No Destination Correspondent",
            contact_type=ContactType.PERSON,
            is_active=True,
        )

        result = promote_correspondent_to_recipient_ready(person)

        self.assertFalse(result.changed)
        self.assertFalse(
            Contact.objects.filter(
                name=SUPPORT_ORGANIZATION_NAME,
                contact_type=ContactType.ORGANIZATION,
            ).exists()
        )
        self.assertFalse(
            OrganizationRoleAssignment.objects.filter(
                role=OrganizationRole.RECIPIENT,
                is_active=True,
            ).exists()
        )
