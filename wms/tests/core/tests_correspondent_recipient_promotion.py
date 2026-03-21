from django.test import TestCase

from contacts.models import Contact, ContactType
from wms.default_shipper_bindings import suppress_default_shipper_binding_sync
from wms.models import (
    Destination,
    ShipmentRecipientOrganization,
    ShipmentShipperRecipientLink,
    ShipmentValidationStatus,
)
from wms.shipment_party_setup import ensure_shipment_shipper


class CorrespondentRecipientPromotionTests(TestCase):
    def _create_default_shipper(self):
        organization = Contact.objects.create(
            name="AVIATION SANS FRONTIERES",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        return ensure_shipment_shipper(
            organization,
            validation_status=ShipmentValidationStatus.VALIDATED,
        )

    def test_ensure_destination_correspondent_recipient_ready_skips_asf_links_when_sync_suppressed(
        self,
    ):
        from contacts.correspondent_recipient_promotion import (
            SUPPORT_ORGANIZATION_NAME,
            ensure_destination_correspondent_recipient_ready,
        )

        shipper = self._create_default_shipper()
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
            result = ensure_destination_correspondent_recipient_ready(destination)

        correspondent.refresh_from_db()
        support_organization = Contact.objects.get(
            name=SUPPORT_ORGANIZATION_NAME,
            contact_type=ContactType.ORGANIZATION,
        )
        self.assertEqual(correspondent.organization, support_organization)
        self.assertTrue(result.shipment_recipient_created)
        self.assertTrue(
            ShipmentRecipientOrganization.objects.filter(
                organization=support_organization,
                destination=destination,
                is_correspondent=True,
                is_active=True,
            ).exists()
        )
        self.assertFalse(
            ShipmentShipperRecipientLink.objects.filter(
                shipper=shipper,
                recipient_organization__organization=support_organization,
                recipient_organization__destination=destination,
                is_active=True,
            ).exists()
        )

    def test_ensure_destination_correspondent_recipient_ready_keeps_existing_active_shipment_party(
        self,
    ):
        from contacts.correspondent_recipient_promotion import (
            ensure_destination_correspondent_recipient_ready,
        )

        organization = Contact.objects.create(
            name="Correspondent Org",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        correspondent = Contact.objects.create(
            name="Correspondent Person",
            contact_type=ContactType.PERSON,
            is_active=True,
        )
        destination = Destination.objects.create(
            city="Niamey",
            iata_code="NIM",
            country="Niger",
            correspondent_contact=correspondent,
            is_active=True,
        )
        ShipmentRecipientOrganization.objects.create(
            organization=organization,
            destination=destination,
            validation_status=ShipmentValidationStatus.VALIDATED,
            is_correspondent=True,
            is_active=True,
        )

        result = ensure_destination_correspondent_recipient_ready(destination)

        correspondent.refresh_from_db()
        self.assertFalse(result.changed)
        self.assertIsNone(correspondent.organization_id)

    def test_ensure_destination_correspondent_recipient_ready_skips_inactive_existing_party(self):
        from contacts.correspondent_recipient_promotion import (
            ensure_destination_correspondent_recipient_ready,
        )

        organization = Contact.objects.create(
            name="Inactive Correspondent Org",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        correspondent = Contact.objects.create(
            name="Inactive Correspondent Person",
            contact_type=ContactType.PERSON,
            is_active=True,
        )
        destination = Destination.objects.create(
            city="Bujumbura",
            iata_code="BJM",
            country="Burundi",
            correspondent_contact=correspondent,
            is_active=True,
        )
        ShipmentRecipientOrganization.objects.create(
            organization=organization,
            destination=destination,
            validation_status=ShipmentValidationStatus.VALIDATED,
            is_correspondent=True,
            is_active=False,
        )

        result = ensure_destination_correspondent_recipient_ready(destination)

        correspondent.refresh_from_db()
        self.assertFalse(result.changed)
        self.assertIsNone(correspondent.organization_id)

    def test_promote_correspondent_org_creates_validated_correspondent_recipient(self):
        from contacts.correspondent_recipient_promotion import (
            promote_correspondent_to_recipient_ready,
        )

        organization = Contact.objects.create(
            name="Correspondent Org",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        destination = Destination.objects.create(
            city="Douala",
            iata_code="DLA",
            country="Cameroun",
            correspondent_contact=organization,
            is_active=True,
        )

        result = promote_correspondent_to_recipient_ready(organization)

        self.assertTrue(result.shipment_recipient_created)
        self.assertTrue(
            ShipmentRecipientOrganization.objects.filter(
                organization=organization,
                destination=destination,
                validation_status=ShipmentValidationStatus.VALIDATED,
                is_correspondent=True,
                is_active=True,
            ).exists()
        )

    def test_promote_person_without_org_attaches_support_org_and_creates_recipient(self):
        from contacts.correspondent_recipient_promotion import (
            SUPPORT_ORGANIZATION_NAME,
            promote_correspondent_to_recipient_ready,
        )

        person = Contact.objects.create(
            name="Standalone Correspondent",
            contact_type=ContactType.PERSON,
            is_active=True,
        )
        destination = Destination.objects.create(
            city="Bangui",
            iata_code="BGF",
            country="RCA",
            correspondent_contact=person,
            is_active=True,
        )

        result = promote_correspondent_to_recipient_ready(person)

        person.refresh_from_db()
        support_organization = Contact.objects.get(
            name=SUPPORT_ORGANIZATION_NAME,
            contact_type=ContactType.ORGANIZATION,
        )
        self.assertEqual(person.organization, support_organization)
        self.assertTrue(result.support_organization_created)
        self.assertTrue(result.attached_to_support_organization)
        self.assertTrue(result.shipment_recipient_created)
        self.assertTrue(
            ShipmentRecipientOrganization.objects.filter(
                organization=support_organization,
                destination=destination,
                is_correspondent=True,
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
        destination = Destination.objects.create(
            city="Bamako",
            iata_code="BKO",
            country="Mali",
            correspondent_contact=person,
            is_active=True,
        )

        result = promote_correspondent_to_recipient_ready(person)

        person.refresh_from_db()
        self.assertEqual(person.organization, organization)
        self.assertFalse(result.support_organization_created)
        self.assertFalse(result.attached_to_support_organization)
        self.assertTrue(
            ShipmentRecipientOrganization.objects.filter(
                organization=organization,
                destination=destination,
                is_correspondent=True,
                is_active=True,
            ).exists()
        )
        self.assertFalse(
            Contact.objects.filter(
                name=SUPPORT_ORGANIZATION_NAME,
                contact_type=ContactType.ORGANIZATION,
            ).exists()
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
        self.assertFalse(ShipmentRecipientOrganization.objects.exists())
