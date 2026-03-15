from django.test import TestCase

from contacts.models import Contact, ContactTag, ContactType
from wms.models import OrganizationRole, OrganizationRoleAssignment


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
