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
