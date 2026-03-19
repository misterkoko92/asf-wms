from django.test import TestCase

from contacts.models import Contact, ContactType
from wms.models import (
    Destination,
    ShipmentAuthorizedRecipientContact,
    ShipmentRecipientContact,
    ShipmentRecipientOrganization,
    ShipmentShipper,
    ShipmentShipperRecipientLink,
    ShipmentValidationStatus,
)
from wms.shipment_party_registry import (
    default_recipient_contact_for_link,
    eligible_recipient_contacts_for_link,
    eligible_recipient_organizations_for_shipper,
    eligible_shippers_for_stopover,
    stopover_correspondent_recipient_organization,
)


class ShipmentPartyRegistryTests(TestCase):
    def _create_organization(self, name: str) -> Contact:
        return Contact.objects.create(
            name=name,
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )

    def _create_person(self, *, organization: Contact, first_name: str, last_name: str) -> Contact:
        return Contact.objects.create(
            name=f"{first_name} {last_name}",
            contact_type=ContactType.PERSON,
            first_name=first_name,
            last_name=last_name,
            organization=organization,
            is_active=True,
        )

    def _create_destination(self, iata_code: str) -> Destination:
        correspondent = self._create_organization(f"Correspondent {iata_code}")
        return Destination.objects.create(
            city=f"City {iata_code}",
            iata_code=iata_code,
            country="Country",
            correspondent_contact=correspondent,
            is_active=True,
        )

    def _create_shipper(
        self,
        *,
        name: str,
        can_send_to_all: bool = False,
        is_active: bool = True,
        validation_status: str = ShipmentValidationStatus.VALIDATED,
    ) -> ShipmentShipper:
        organization = self._create_organization(name)
        default_contact = self._create_person(
            organization=organization,
            first_name="Default",
            last_name=name.replace(" ", ""),
        )
        return ShipmentShipper.objects.create(
            organization=organization,
            default_contact=default_contact,
            can_send_to_all=can_send_to_all,
            is_active=is_active,
            validation_status=validation_status,
        )

    def _create_recipient_organization(
        self,
        *,
        name: str,
        destination: Destination,
        is_correspondent: bool = False,
        is_active: bool = True,
        validation_status: str = ShipmentValidationStatus.VALIDATED,
    ) -> ShipmentRecipientOrganization:
        organization = self._create_organization(name)
        return ShipmentRecipientOrganization.objects.create(
            organization=organization,
            destination=destination,
            validation_status=validation_status,
            is_correspondent=is_correspondent,
            is_active=is_active,
        )

    def test_eligible_shippers_for_stopover_includes_linked_and_can_send_to_all(self):
        destination_a = self._create_destination("ABJ")
        destination_b = self._create_destination("DKR")

        linked_shipper = self._create_shipper(name="Linked shipper")
        global_shipper = self._create_shipper(name="Global shipper", can_send_to_all=True)
        self._create_shipper(name="Inactive shipper", is_active=False)
        self._create_shipper(
            name="Pending shipper",
            validation_status=ShipmentValidationStatus.PENDING,
        )
        other_shipper = self._create_shipper(name="Other shipper")

        recipient_a = self._create_recipient_organization(
            name="Recipient A",
            destination=destination_a,
        )
        recipient_b = self._create_recipient_organization(
            name="Recipient B",
            destination=destination_b,
        )
        ShipmentShipperRecipientLink.objects.create(
            shipper=linked_shipper,
            recipient_organization=recipient_a,
            is_active=True,
        )
        ShipmentShipperRecipientLink.objects.create(
            shipper=other_shipper,
            recipient_organization=recipient_b,
            is_active=True,
        )

        shipper_ids = set(
            eligible_shippers_for_stopover(destination_a).values_list("id", flat=True)
        )
        self.assertIn(linked_shipper.id, shipper_ids)
        self.assertIn(global_shipper.id, shipper_ids)
        self.assertNotIn(other_shipper.id, shipper_ids)

    def test_eligible_recipient_organizations_for_shipper_filters_active_link_and_stopover(self):
        destination = self._create_destination("CMN")
        shipper = self._create_shipper(name="Shipper CMN")
        recipient_allowed = self._create_recipient_organization(
            name="Recipient Allowed",
            destination=destination,
        )
        recipient_pending = self._create_recipient_organization(
            name="Recipient Pending",
            destination=destination,
            validation_status=ShipmentValidationStatus.PENDING,
        )
        recipient_inactive_link = self._create_recipient_organization(
            name="Recipient Inactive Link",
            destination=destination,
        )
        recipient_other_stopover = self._create_recipient_organization(
            name="Recipient Other Stopover",
            destination=self._create_destination("NBO"),
        )

        ShipmentShipperRecipientLink.objects.create(
            shipper=shipper,
            recipient_organization=recipient_allowed,
            is_active=True,
        )
        ShipmentShipperRecipientLink.objects.create(
            shipper=shipper,
            recipient_organization=recipient_pending,
            is_active=True,
        )
        ShipmentShipperRecipientLink.objects.create(
            shipper=shipper,
            recipient_organization=recipient_inactive_link,
            is_active=False,
        )
        ShipmentShipperRecipientLink.objects.create(
            shipper=shipper,
            recipient_organization=recipient_other_stopover,
            is_active=True,
        )

        recipient_ids = set(
            eligible_recipient_organizations_for_shipper(
                shipper=shipper,
                destination=destination,
            ).values_list("id", flat=True)
        )
        self.assertEqual(recipient_ids, {recipient_allowed.id})

    def test_eligible_recipient_organizations_for_shipper_honors_can_send_to_all(self):
        destination = self._create_destination("LFW")
        global_shipper = self._create_shipper(
            name="ASF Global",
            can_send_to_all=True,
        )
        recipient_one = self._create_recipient_organization(
            name="Recipient One",
            destination=destination,
        )
        recipient_two = self._create_recipient_organization(
            name="Recipient Two",
            destination=destination,
        )
        self._create_recipient_organization(
            name="Recipient Pending",
            destination=destination,
            validation_status=ShipmentValidationStatus.PENDING,
        )
        self._create_recipient_organization(
            name="Recipient Inactive",
            destination=destination,
            is_active=False,
        )

        recipient_ids = set(
            eligible_recipient_organizations_for_shipper(
                shipper=global_shipper,
                destination=destination,
            ).values_list("id", flat=True)
        )

        self.assertEqual(recipient_ids, {recipient_one.id, recipient_two.id})

    def test_eligible_recipient_organizations_for_shipper_requires_active_shipper_organization(
        self,
    ):
        destination = self._create_destination("TNR")
        shipper = self._create_shipper(name="Shipper TNR")
        recipient = self._create_recipient_organization(
            name="Recipient TNR",
            destination=destination,
        )
        ShipmentShipperRecipientLink.objects.create(
            shipper=shipper,
            recipient_organization=recipient,
            is_active=True,
        )

        shipper.organization.is_active = False
        shipper.organization.save(update_fields=["is_active"])

        self.assertEqual(
            eligible_recipient_organizations_for_shipper(
                shipper=shipper,
                destination=destination,
            ).count(),
            0,
        )

    def test_eligible_recipient_contacts_for_link_returns_only_active_authorized_contacts(self):
        destination = self._create_destination("DLA")
        shipper = self._create_shipper(name="Shipper DLA")
        recipient = self._create_recipient_organization(
            name="Recipient DLA",
            destination=destination,
        )
        link = ShipmentShipperRecipientLink.objects.create(
            shipper=shipper,
            recipient_organization=recipient,
            is_active=True,
        )
        active_contact = ShipmentRecipientContact.objects.create(
            recipient_organization=recipient,
            contact=self._create_person(
                organization=recipient.organization,
                first_name="Jean",
                last_name="Actif",
            ),
            is_active=True,
        )
        inactive_authorization_contact = ShipmentRecipientContact.objects.create(
            recipient_organization=recipient,
            contact=self._create_person(
                organization=recipient.organization,
                first_name="Paul",
                last_name="InactiveAuthorization",
            ),
            is_active=True,
        )
        ShipmentAuthorizedRecipientContact.objects.create(
            link=link,
            recipient_contact=active_contact,
            is_default=True,
            is_active=True,
        )
        ShipmentAuthorizedRecipientContact.objects.create(
            link=link,
            recipient_contact=inactive_authorization_contact,
            is_default=False,
            is_active=False,
        )

        contact_ids = set(eligible_recipient_contacts_for_link(link).values_list("id", flat=True))
        self.assertEqual(contact_ids, {active_contact.id})

    def test_default_recipient_contact_for_link_returns_active_default(self):
        destination = self._create_destination("NSI")
        shipper = self._create_shipper(name="Shipper NSI")
        recipient = self._create_recipient_organization(
            name="Recipient NSI",
            destination=destination,
        )
        link = ShipmentShipperRecipientLink.objects.create(
            shipper=shipper,
            recipient_organization=recipient,
            is_active=True,
        )
        non_default = ShipmentRecipientContact.objects.create(
            recipient_organization=recipient,
            contact=self._create_person(
                organization=recipient.organization,
                first_name="Alice",
                last_name="NonDefault",
            ),
            is_active=True,
        )
        default_contact = ShipmentRecipientContact.objects.create(
            recipient_organization=recipient,
            contact=self._create_person(
                organization=recipient.organization,
                first_name="Bob",
                last_name="Default",
            ),
            is_active=True,
        )
        ShipmentAuthorizedRecipientContact.objects.create(
            link=link,
            recipient_contact=non_default,
            is_default=False,
            is_active=True,
        )
        ShipmentAuthorizedRecipientContact.objects.create(
            link=link,
            recipient_contact=default_contact,
            is_default=True,
            is_active=True,
        )

        self.assertEqual(default_recipient_contact_for_link(link), default_contact)

    def test_recipient_contact_registry_ignores_non_valid_recipient_organization(self):
        destination = self._create_destination("GAO")
        shipper = self._create_shipper(name="Shipper GAO")
        recipient = self._create_recipient_organization(
            name="Recipient GAO",
            destination=destination,
        )
        link = ShipmentShipperRecipientLink.objects.create(
            shipper=shipper,
            recipient_organization=recipient,
            is_active=True,
        )
        default_contact = ShipmentRecipientContact.objects.create(
            recipient_organization=recipient,
            contact=self._create_person(
                organization=recipient.organization,
                first_name="Fatou",
                last_name="Default",
            ),
            is_active=True,
        )
        ShipmentAuthorizedRecipientContact.objects.create(
            link=link,
            recipient_contact=default_contact,
            is_default=True,
            is_active=True,
        )

        recipient.validation_status = ShipmentValidationStatus.PENDING
        recipient.save(update_fields=["validation_status"])

        self.assertEqual(eligible_recipient_contacts_for_link(link).count(), 0)
        self.assertIsNone(default_recipient_contact_for_link(link))

    def test_stopover_correspondent_recipient_organization_returns_active_correspondent(self):
        destination = self._create_destination("BKO")
        correspondent = self._create_recipient_organization(
            name="Correspondent BKO",
            destination=destination,
            is_correspondent=True,
            is_active=True,
        )
        self._create_recipient_organization(
            name="Recipient BKO",
            destination=destination,
            is_correspondent=False,
            is_active=True,
        )

        self.assertEqual(
            stopover_correspondent_recipient_organization(destination),
            correspondent,
        )
