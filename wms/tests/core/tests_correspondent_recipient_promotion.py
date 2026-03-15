from django.test import TestCase

from contacts.models import Contact, ContactTag, ContactType
from wms.models import Destination, OrganizationRole, OrganizationRoleAssignment


class CorrespondentRecipientPromotionTests(TestCase):
    def test_promote_correspondent_org_adds_recipient_tag_and_role(self):
        from contacts.correspondent_recipient_promotion import (
            promote_correspondent_to_recipient_ready,
        )

        correspondent_tag = ContactTag.objects.create(name="correspondant")
        organization = Contact.objects.create(
            name="Correspondent Org",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )

        promote_correspondent_to_recipient_ready(organization, tags=[correspondent_tag])

        self.assertTrue(organization.tags.filter(name__iexact="destinataire").exists())
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

        correspondent_tag = ContactTag.objects.create(name="correspondant")
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

        promote_correspondent_to_recipient_ready(person, tags=[correspondent_tag])

        person.refresh_from_db()
        support_organization = Contact.objects.get(
            name=SUPPORT_ORGANIZATION_NAME,
            contact_type=ContactType.ORGANIZATION,
        )
        self.assertEqual(person.organization, support_organization)
        self.assertEqual(
            set(person.destinations.values_list("id", flat=True)),
            {destination.id},
        )
        self.assertEqual(person.destination_id, destination.id)

    def test_promote_correspondent_org_scopes_multiple_destinations_and_clears_legacy_field(self):
        from contacts.correspondent_recipient_promotion import (
            promote_correspondent_to_recipient_ready,
        )

        correspondent_tag = ContactTag.objects.create(name="correspondant")
        organization = Contact.objects.create(
            name="Scoped Correspondent Org",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        destination_abj = Destination.objects.create(
            city="Abidjan",
            iata_code="ABJ",
            country="Cote d'Ivoire",
            correspondent_contact=organization,
            is_active=True,
        )
        destination_dkr = Destination.objects.create(
            city="Dakar",
            iata_code="DKR",
            country="Senegal",
            correspondent_contact=organization,
            is_active=True,
        )

        promote_correspondent_to_recipient_ready(organization, tags=[correspondent_tag])

        organization.refresh_from_db()
        self.assertEqual(
            set(organization.destinations.values_list("id", flat=True)),
            {destination_abj.id, destination_dkr.id},
        )
        self.assertIsNone(organization.destination_id)

    def test_promote_person_with_org_reuses_existing_org(self):
        from contacts.correspondent_recipient_promotion import (
            SUPPORT_ORGANIZATION_NAME,
            promote_correspondent_to_recipient_ready,
        )

        correspondent_tag = ContactTag.objects.create(name="correspondant")
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

        promote_correspondent_to_recipient_ready(person, tags=[correspondent_tag])

        person.refresh_from_db()
        self.assertEqual(person.organization, organization)
        self.assertFalse(
            Contact.objects.filter(
                name=SUPPORT_ORGANIZATION_NAME,
                contact_type=ContactType.ORGANIZATION,
            ).exists()
        )
        self.assertTrue(person.tags.filter(name__iexact="destinataire").exists())
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

        correspondent_tag = ContactTag.objects.create(name="correspondant")
        person = Contact.objects.create(
            name="Standalone Correspondent",
            contact_type=ContactType.PERSON,
            is_active=True,
        )

        promote_correspondent_to_recipient_ready(person, tags=[correspondent_tag])

        person.refresh_from_db()
        support_organization = Contact.objects.get(
            name=SUPPORT_ORGANIZATION_NAME,
            contact_type=ContactType.ORGANIZATION,
        )
        self.assertEqual(person.organization, support_organization)
        self.assertTrue(person.tags.filter(name__iexact="destinataire").exists())
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

        correspondent_tag = ContactTag.objects.create(name="correspondant")
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

        promote_correspondent_to_recipient_ready(first, tags=[correspondent_tag])
        promote_correspondent_to_recipient_ready(second, tags=[correspondent_tag])

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

    def test_adding_correspondent_tag_triggers_promotion(self):
        from contacts.correspondent_recipient_promotion import SUPPORT_ORGANIZATION_NAME

        correspondent_tag = ContactTag.objects.create(name="correspondant")
        person = Contact.objects.create(
            name="Signal Correspondent",
            contact_type=ContactType.PERSON,
            is_active=True,
        )

        person.tags.add(correspondent_tag)

        person.refresh_from_db()
        support_organization = Contact.objects.get(
            name=SUPPORT_ORGANIZATION_NAME,
            contact_type=ContactType.ORGANIZATION,
        )
        self.assertEqual(person.organization, support_organization)
        self.assertTrue(person.tags.filter(name__iexact="destinataire").exists())
        self.assertTrue(
            OrganizationRoleAssignment.objects.filter(
                organization=support_organization,
                role=OrganizationRole.RECIPIENT,
                is_active=True,
            ).exists()
        )

    def test_readding_tags_is_idempotent(self):
        from contacts.correspondent_recipient_promotion import SUPPORT_ORGANIZATION_NAME

        correspondent_tag = ContactTag.objects.create(name="correspondant")
        unrelated_tag = ContactTag.objects.create(name="autre")
        person = Contact.objects.create(
            name="Idempotent Correspondent",
            contact_type=ContactType.PERSON,
            is_active=True,
        )

        person.tags.add(correspondent_tag)
        support_org = Contact.objects.get(
            name=SUPPORT_ORGANIZATION_NAME,
            contact_type=ContactType.ORGANIZATION,
        )

        person.tags.add(unrelated_tag)

        self.assertEqual(
            Contact.objects.filter(
                name=SUPPORT_ORGANIZATION_NAME,
                contact_type=ContactType.ORGANIZATION,
            ).count(),
            1,
        )
        self.assertEqual(
            OrganizationRoleAssignment.objects.filter(
                organization=support_org,
                role=OrganizationRole.RECIPIENT,
            ).count(),
            1,
        )

    def test_removing_correspondent_tag_does_not_remove_recipient_tag(self):
        correspondent_tag = ContactTag.objects.create(name="correspondant")
        person = Contact.objects.create(
            name="Removal Correspondent",
            contact_type=ContactType.PERSON,
            is_active=True,
        )

        person.tags.add(correspondent_tag)
        person.tags.remove(correspondent_tag)

        self.assertTrue(person.tags.filter(name__iexact="destinataire").exists())

    def test_removing_correspondent_tag_does_not_remove_recipient_role(self):
        from contacts.correspondent_recipient_promotion import SUPPORT_ORGANIZATION_NAME

        correspondent_tag = ContactTag.objects.create(name="correspondant")
        person = Contact.objects.create(
            name="Removal Role Correspondent",
            contact_type=ContactType.PERSON,
            is_active=True,
        )

        person.tags.add(correspondent_tag)
        support_org = Contact.objects.get(
            name=SUPPORT_ORGANIZATION_NAME,
            contact_type=ContactType.ORGANIZATION,
        )

        person.tags.remove(correspondent_tag)

        self.assertTrue(
            OrganizationRoleAssignment.objects.filter(
                organization=support_org,
                role=OrganizationRole.RECIPIENT,
                is_active=True,
            ).exists()
        )
