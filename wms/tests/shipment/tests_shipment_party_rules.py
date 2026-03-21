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
from wms.shipment_party_rules import (
    MESSAGE_RECIPIENT_BINDING_MISSING,
    MESSAGE_RECIPIENT_REVIEW_PENDING,
    MESSAGE_SHIPPER_OUT_OF_SCOPE,
    MESSAGE_SHIPPER_REVIEW_PENDING,
    OrganizationRoleResolutionError,
    build_party_contact_reference,
    eligible_correspondent_contacts_for_destination,
    eligible_recipient_contacts_for_shipper_destination,
    eligible_shipper_contacts_for_destination,
    normalize_party_contact_to_org,
    resolve_recipient_binding_for_operation,
    resolve_shipper_for_operation,
)


class ShipmentPartyRulesTests(TestCase):
    def _create_org(self, name: str) -> Contact:
        return Contact.objects.create(
            name=name,
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )

    def _create_person(self, name: str, *, organization: Contact | None = None) -> Contact:
        return Contact.objects.create(
            name=name,
            contact_type=ContactType.PERSON,
            first_name=name.split()[0],
            last_name=name.split()[-1],
            organization=organization,
            is_active=True,
        )

    def _create_destination(self, iata: str, correspondent: Contact) -> Destination:
        return Destination.objects.create(
            city=f"City {iata}",
            iata_code=iata,
            country="Country",
            correspondent_contact=correspondent,
            is_active=True,
        )

    def _create_shipper(
        self,
        organization: Contact,
        *,
        default_contact: Contact | None,
        validation_status: str = ShipmentValidationStatus.VALIDATED,
        can_send_to_all: bool = False,
        is_active: bool = True,
    ) -> ShipmentShipper:
        return ShipmentShipper.objects.create(
            organization=organization,
            default_contact=default_contact,
            validation_status=validation_status,
            can_send_to_all=can_send_to_all,
            is_active=is_active,
        )

    def _create_recipient_organization(
        self,
        organization: Contact,
        *,
        destination: Destination,
        validation_status: str = ShipmentValidationStatus.VALIDATED,
        is_correspondent: bool = False,
        is_active: bool = True,
    ) -> ShipmentRecipientOrganization:
        return ShipmentRecipientOrganization.objects.create(
            organization=organization,
            destination=destination,
            validation_status=validation_status,
            is_correspondent=is_correspondent,
            is_active=is_active,
        )

    def _create_recipient_contact(
        self,
        recipient_organization: ShipmentRecipientOrganization,
        *,
        contact: Contact,
        is_active: bool = True,
    ) -> ShipmentRecipientContact:
        return ShipmentRecipientContact.objects.create(
            recipient_organization=recipient_organization,
            contact=contact,
            is_active=is_active,
        )

    def _authorize_recipient_contact(
        self,
        *,
        link: ShipmentShipperRecipientLink,
        recipient_contact: ShipmentRecipientContact,
        is_default: bool = False,
        is_active: bool = True,
    ) -> ShipmentAuthorizedRecipientContact:
        return ShipmentAuthorizedRecipientContact.objects.create(
            link=link,
            recipient_contact=recipient_contact,
            is_default=is_default,
            is_active=is_active,
        )

    def test_normalize_party_contact_to_org_uses_person_organization(self):
        organization = self._create_org("Recipient Org")
        person = self._create_person("Recipient Person", organization=organization)

        self.assertEqual(normalize_party_contact_to_org(person), organization)

    def test_eligible_shipper_contacts_for_destination_returns_org_and_default_contact(self):
        correspondent = self._create_org("Correspondent CMN")
        destination = self._create_destination("CMN", correspondent)
        other_destination = self._create_destination("NBO", correspondent)
        shipper_org = self._create_org("Shipper In Scope")
        shipper_person = self._create_person("Shipper Person", organization=shipper_org)
        shipper_out_org = self._create_org("Shipper Out Scope")
        shipper_out_person = self._create_person("Shipper Out Person", organization=shipper_out_org)

        shipper = self._create_shipper(shipper_org, default_contact=shipper_person)
        self._create_shipper(shipper_out_org, default_contact=shipper_out_person)
        recipient_org = self._create_recipient_organization(
            self._create_org("Recipient Allowed"),
            destination=destination,
        )
        other_recipient_org = self._create_recipient_organization(
            self._create_org("Recipient Other"),
            destination=other_destination,
        )
        ShipmentShipperRecipientLink.objects.create(
            shipper=shipper,
            recipient_organization=recipient_org,
            is_active=True,
        )
        ShipmentShipperRecipientLink.objects.create(
            shipper=ShipmentShipper.objects.get(organization=shipper_out_org),
            recipient_organization=other_recipient_org,
            is_active=True,
        )

        shipper_ids = set(
            eligible_shipper_contacts_for_destination(destination).values_list("id", flat=True)
        )

        self.assertIn(shipper_org.id, shipper_ids)
        self.assertIn(shipper_person.id, shipper_ids)
        self.assertNotIn(shipper_out_org.id, shipper_ids)
        self.assertNotIn(shipper_out_person.id, shipper_ids)

    def test_eligible_recipient_contacts_for_shipper_destination_returns_org_and_authorized_people(
        self,
    ):
        correspondent = self._create_org("Correspondent BKO")
        destination = self._create_destination("BKO", correspondent)
        shipper_org = self._create_org("Shipper BKO")
        shipper_person = self._create_person("Shipper Person", organization=shipper_org)
        recipient_org = self._create_org("Recipient Allowed")
        recipient_person = self._create_person("Recipient Person", organization=recipient_org)
        blocked_org = self._create_org("Recipient Blocked")
        blocked_person = self._create_person("Blocked Person", organization=blocked_org)

        shipper = self._create_shipper(
            shipper_org,
            default_contact=shipper_person,
        )
        recipient = self._create_recipient_organization(recipient_org, destination=destination)
        blocked = self._create_recipient_organization(blocked_org, destination=destination)
        recipient_contact = self._create_recipient_contact(recipient, contact=recipient_person)
        self._create_recipient_contact(blocked, contact=blocked_person)
        link = ShipmentShipperRecipientLink.objects.create(
            shipper=shipper,
            recipient_organization=recipient,
            is_active=True,
        )
        self._authorize_recipient_contact(link=link, recipient_contact=recipient_contact)

        recipient_ids = set(
            eligible_recipient_contacts_for_shipper_destination(
                shipper_contact=shipper_person,
                destination=destination,
            ).values_list("id", flat=True)
        )

        self.assertIn(recipient_org.id, recipient_ids)
        self.assertIn(recipient_person.id, recipient_ids)
        self.assertNotIn(blocked_org.id, recipient_ids)
        self.assertNotIn(blocked_person.id, recipient_ids)

    def test_eligible_correspondent_contacts_for_destination_returns_org_and_active_people(self):
        correspondent_org = self._create_org("Correspondent DLA")
        correspondent_person = self._create_person(
            "Cora Correspondent",
            organization=correspondent_org,
        )
        destination = self._create_destination("DLA", correspondent_person)
        recipient_organization = self._create_recipient_organization(
            correspondent_org,
            destination=destination,
            is_correspondent=True,
        )
        self._create_recipient_contact(
            recipient_organization,
            contact=correspondent_person,
            is_active=True,
        )

        correspondent_ids = set(
            eligible_correspondent_contacts_for_destination(destination).values_list(
                "id", flat=True
            )
        )

        self.assertEqual(correspondent_ids, {correspondent_org.id, correspondent_person.id})

    def test_resolve_shipper_for_operation_rejects_unvalidated_or_out_of_scope_shipper(self):
        correspondent = self._create_org("Correspondent ACC")
        destination = self._create_destination("ACC", correspondent)
        other_destination = self._create_destination("CMN", correspondent)
        shipper_org = self._create_org("Shipper Pending")
        shipper_person = self._create_person("Shipper Contact", organization=shipper_org)
        out_scope_org = self._create_org("Shipper Out Scope")
        out_scope_person = self._create_person("Out Scope Contact", organization=out_scope_org)

        pending_shipper = self._create_shipper(
            shipper_org,
            default_contact=shipper_person,
            validation_status=ShipmentValidationStatus.PENDING,
        )
        out_scope_shipper = self._create_shipper(out_scope_org, default_contact=out_scope_person)
        other_recipient = self._create_recipient_organization(
            self._create_org("Recipient Other"),
            destination=other_destination,
        )
        ShipmentShipperRecipientLink.objects.create(
            shipper=out_scope_shipper,
            recipient_organization=other_recipient,
            is_active=True,
        )

        with self.assertRaisesMessage(
            OrganizationRoleResolutionError,
            MESSAGE_SHIPPER_REVIEW_PENDING,
        ):
            resolve_shipper_for_operation(
                shipper_org=pending_shipper.organization, destination=destination
            )

        with self.assertRaisesMessage(
            OrganizationRoleResolutionError,
            MESSAGE_SHIPPER_OUT_OF_SCOPE,
        ):
            resolve_shipper_for_operation(
                shipper_org=out_scope_shipper.organization, destination=destination
            )

    def test_resolve_recipient_binding_for_operation_rejects_missing_or_unvalidated_recipient(self):
        correspondent = self._create_org("Correspondent LFW")
        destination = self._create_destination("LFW", correspondent)
        shipper_org = self._create_org("Shipper LFW")
        shipper_person = self._create_person("Shipper Contact", organization=shipper_org)
        recipient_org = self._create_org("Recipient LFW")
        shipper = self._create_shipper(
            shipper_org,
            default_contact=shipper_person,
            can_send_to_all=True,
        )
        recipient = self._create_recipient_organization(
            recipient_org,
            destination=destination,
            validation_status=ShipmentValidationStatus.PENDING,
        )
        ShipmentShipperRecipientLink.objects.create(
            shipper=shipper,
            recipient_organization=recipient,
            is_active=True,
        )

        with self.assertRaisesMessage(
            OrganizationRoleResolutionError,
            MESSAGE_RECIPIENT_REVIEW_PENDING,
        ):
            resolve_recipient_binding_for_operation(
                shipper_org=shipper_org,
                recipient_org=recipient_org,
                destination=destination,
            )

        other_org = self._create_org("Recipient Missing")
        with self.assertRaisesMessage(
            OrganizationRoleResolutionError,
            MESSAGE_RECIPIENT_BINDING_MISSING,
        ):
            resolve_recipient_binding_for_operation(
                shipper_org=shipper_org,
                recipient_org=other_org,
                destination=destination,
            )

    def test_build_party_contact_reference_keeps_stable_shape_without_contact(self):
        reference = build_party_contact_reference(None, fallback_name="Fallback Contact")

        self.assertEqual(
            reference,
            {
                "contact_id": None,
                "contact_name": "Fallback Contact",
                "notification_emails": [],
            },
        )
