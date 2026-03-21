from django.test import TestCase

from contacts.models import Contact, ContactType
from wms.default_shipper_bindings import (
    _resolve_default_shipper,
    ensure_default_shipper_bindings_for_destination_id,
    ensure_default_shipper_bindings_for_recipient_assignment_id,
    ensure_default_shipper_links_for_destination_id,
    ensure_default_shipper_links_for_recipient_organization_id,
    suppress_default_shipper_binding_sync,
)
from wms.models import (
    Destination,
    ShipmentAuthorizedRecipientContact,
    ShipmentRecipientContact,
    ShipmentRecipientOrganization,
    ShipmentShipperRecipientLink,
    ShipmentValidationStatus,
)
from wms.shipment_party_setup import ensure_shipment_shipper


class DefaultShipperBindingsHelpersTests(TestCase):
    def _create_org(self, name: str) -> Contact:
        return Contact.objects.create(
            name=name,
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )

    def _create_default_shipper(self):
        organization = self._create_org("AVIATION SANS FRONTIERES")
        return ensure_shipment_shipper(
            organization,
            validation_status=ShipmentValidationStatus.VALIDATED,
        )

    def _create_destination(self, iata: str) -> Destination:
        correspondent = Contact.objects.create(
            name=f"Correspondent {iata}",
            contact_type=ContactType.PERSON,
            is_active=True,
        )
        return Destination.objects.create(
            city=f"City {iata}",
            iata_code=iata,
            country="Country",
            correspondent_contact=correspondent,
            is_active=True,
        )

    def _create_recipient_organization(
        self,
        *,
        destination: Destination,
        name: str,
        create_contact: bool = True,
        validation_status: str = ShipmentValidationStatus.VALIDATED,
    ) -> ShipmentRecipientOrganization:
        organization = self._create_org(name)
        recipient_organization = ShipmentRecipientOrganization.objects.create(
            organization=organization,
            destination=destination,
            validation_status=validation_status,
            is_correspondent=False,
            is_active=True,
        )
        if create_contact:
            person = Contact.objects.create(
                name=f"Referent {name}",
                contact_type=ContactType.PERSON,
                organization=organization,
                email=f"{name.lower().replace(' ', '-')}@example.org",
                is_active=True,
            )
            ShipmentRecipientContact.objects.create(
                recipient_organization=recipient_organization,
                contact=person,
                is_active=True,
            )
        return recipient_organization

    def test_resolve_default_shipper_returns_none_without_active_asf_contact(self):
        self.assertIsNone(_resolve_default_shipper())

        inactive = self._create_org("AVIATION SANS FRONTIERES")
        inactive.is_active = False
        inactive.save(update_fields=["is_active"])

        self.assertIsNone(_resolve_default_shipper())

    def test_resolve_default_shipper_promotes_plain_asf_contact_to_validated_shipper(self):
        organization = self._create_org("AVIATION SANS FRONTIERES")

        shipper = _resolve_default_shipper()

        self.assertIsNotNone(shipper)
        self.assertEqual(shipper.organization, organization)
        self.assertEqual(shipper.validation_status, ShipmentValidationStatus.VALIDATED)
        self.assertTrue(shipper.can_send_to_all)
        self.assertIsNotNone(shipper.default_contact_id)

    def test_ensure_default_shipper_links_for_destination_id_creates_links_and_default_contact(
        self,
    ):
        shipper = self._create_default_shipper()
        destination = self._create_destination("CMN")
        recipient = self._create_recipient_organization(
            destination=destination,
            name="Recipient One",
        )

        created = ensure_default_shipper_links_for_destination_id(destination.id)
        created_again = ensure_default_shipper_bindings_for_destination_id(destination.id)

        self.assertEqual(created, 1)
        self.assertEqual(created_again, 0)
        link = ShipmentShipperRecipientLink.objects.get(
            shipper=shipper,
            recipient_organization=recipient,
        )
        self.assertTrue(link.is_active)
        authorization = ShipmentAuthorizedRecipientContact.objects.get(link=link, is_default=True)
        self.assertTrue(authorization.is_active)

    def test_ensure_default_shipper_links_for_destination_id_skips_missing_shipper_or_destination(
        self,
    ):
        self.assertEqual(ensure_default_shipper_links_for_destination_id(999999), 0)

        destination = self._create_destination("DKR")
        self._create_recipient_organization(destination=destination, name="Recipient Missing ASF")
        self.assertEqual(ensure_default_shipper_links_for_destination_id(destination.id), 0)

    def test_ensure_default_shipper_links_for_recipient_organization_id_creates_link(self):
        shipper = self._create_default_shipper()
        destination = self._create_destination("BKO")
        recipient = self._create_recipient_organization(
            destination=destination,
            name="Recipient Direct",
        )

        created = ensure_default_shipper_links_for_recipient_organization_id(recipient.id)
        created_again = ensure_default_shipper_bindings_for_recipient_assignment_id(999999)

        self.assertEqual(created, 1)
        self.assertEqual(created_again, 0)
        self.assertTrue(
            ShipmentShipperRecipientLink.objects.filter(
                shipper=shipper,
                recipient_organization=recipient,
                is_active=True,
            ).exists()
        )

    def test_ensure_default_shipper_links_for_recipient_organization_id_skips_unvalidated_recipient(
        self,
    ):
        self._create_default_shipper()
        destination = self._create_destination("NIM")
        recipient = self._create_recipient_organization(
            destination=destination,
            name="Recipient Pending",
            validation_status=ShipmentValidationStatus.PENDING,
        )

        created = ensure_default_shipper_links_for_recipient_organization_id(recipient.id)

        self.assertEqual(created, 0)
        self.assertFalse(ShipmentShipperRecipientLink.objects.exists())


class DefaultShipperBindingsSignalTests(TestCase):
    def test_sync_can_be_suppressed_without_side_effects(self):
        with suppress_default_shipper_binding_sync():
            self.assertFalse(
                ShipmentShipperRecipientLink.objects.exists(),
            )
