from django.test import TestCase

from contacts.models import Contact, ContactType
from wms.models import (
    Destination,
    OrganizationRole,
    OrganizationRoleAssignment,
    RecipientBinding,
    ShipperScope,
)
from wms.shipment_party_rules import (
    build_party_contact_reference,
    eligible_correspondent_contacts_for_destination,
    eligible_recipient_contacts_for_shipper_destination,
    eligible_shipper_contacts_for_destination,
    normalize_party_contact_to_org,
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

    def test_normalize_party_contact_to_org_uses_person_organization(self):
        organization = self._create_org("Recipient Org")
        person = self._create_person("Recipient Person", organization=organization)

        self.assertEqual(normalize_party_contact_to_org(person), organization)

    def test_eligible_shipper_contacts_for_destination_returns_org_and_person_contacts(self):
        correspondent = self._create_org("Correspondent CMN")
        destination = self._create_destination("CMN", correspondent)
        other_destination = self._create_destination("NBO", correspondent)
        shipper_org = self._create_org("Shipper In Scope")
        shipper_person = self._create_person("Shipper Person", organization=shipper_org)
        shipper_out_org = self._create_org("Shipper Out Scope")
        shipper_out_person = self._create_person("Shipper Out Person", organization=shipper_out_org)

        shipper_assignment = OrganizationRoleAssignment.objects.create(
            organization=shipper_org,
            role=OrganizationRole.SHIPPER,
            is_active=True,
        )
        out_assignment = OrganizationRoleAssignment.objects.create(
            organization=shipper_out_org,
            role=OrganizationRole.SHIPPER,
            is_active=True,
        )
        ShipperScope.objects.create(
            role_assignment=shipper_assignment,
            destination=destination,
            all_destinations=False,
            is_active=True,
        )
        ShipperScope.objects.create(
            role_assignment=out_assignment,
            destination=other_destination,
            all_destinations=False,
            is_active=True,
        )

        shipper_ids = set(
            eligible_shipper_contacts_for_destination(destination).values_list("id", flat=True)
        )

        self.assertIn(shipper_org.id, shipper_ids)
        self.assertIn(shipper_person.id, shipper_ids)
        self.assertNotIn(shipper_out_org.id, shipper_ids)
        self.assertNotIn(shipper_out_person.id, shipper_ids)

    def test_eligible_shipper_contacts_for_destination_reads_org_roles_unconditionally(self):
        correspondent = self._create_org("Correspondent RAK")
        destination = self._create_destination("RAK", correspondent)
        shipper_org = self._create_org("Shipper Runtime Off")
        shipper_person = self._create_person("Shipper Runtime Person", organization=shipper_org)

        shipper_assignment = OrganizationRoleAssignment.objects.create(
            organization=shipper_org,
            role=OrganizationRole.SHIPPER,
            is_active=True,
        )
        ShipperScope.objects.create(
            role_assignment=shipper_assignment,
            destination=destination,
            all_destinations=False,
            is_active=True,
        )

        shipper_ids = set(
            eligible_shipper_contacts_for_destination(destination).values_list("id", flat=True)
        )

        self.assertIn(shipper_org.id, shipper_ids)
        self.assertIn(shipper_person.id, shipper_ids)

    def test_eligible_recipient_contacts_for_shipper_destination_returns_bound_org_and_people(
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

        shipper_assignment = OrganizationRoleAssignment.objects.create(
            organization=shipper_org,
            role=OrganizationRole.SHIPPER,
            is_active=True,
        )
        OrganizationRoleAssignment.objects.create(
            organization=recipient_org,
            role=OrganizationRole.RECIPIENT,
            is_active=True,
        )
        OrganizationRoleAssignment.objects.create(
            organization=blocked_org,
            role=OrganizationRole.RECIPIENT,
            is_active=True,
        )
        ShipperScope.objects.create(
            role_assignment=shipper_assignment,
            destination=destination,
            all_destinations=False,
            is_active=True,
        )
        RecipientBinding.objects.create(
            shipper_org=shipper_org,
            recipient_org=recipient_org,
            destination=destination,
            is_active=True,
        )

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

    def test_eligible_recipient_contacts_for_shipper_destination_reads_org_roles_unconditionally(
        self,
    ):
        correspondent = self._create_org("Correspondent DKR")
        destination = self._create_destination("DKR", correspondent)
        shipper_org = self._create_org("Shipper Runtime Recipient")
        shipper_person = self._create_person("Shipper Runtime Person", organization=shipper_org)
        recipient_org = self._create_org("Recipient Runtime Allowed")
        recipient_person = self._create_person(
            "Recipient Runtime Person", organization=recipient_org
        )

        shipper_assignment = OrganizationRoleAssignment.objects.create(
            organization=shipper_org,
            role=OrganizationRole.SHIPPER,
            is_active=True,
        )
        OrganizationRoleAssignment.objects.create(
            organization=recipient_org,
            role=OrganizationRole.RECIPIENT,
            is_active=True,
        )
        ShipperScope.objects.create(
            role_assignment=shipper_assignment,
            destination=destination,
            all_destinations=False,
            is_active=True,
        )
        RecipientBinding.objects.create(
            shipper_org=shipper_org,
            recipient_org=recipient_org,
            destination=destination,
            is_active=True,
        )

        recipient_ids = set(
            eligible_recipient_contacts_for_shipper_destination(
                shipper_contact=shipper_person,
                destination=destination,
            ).values_list("id", flat=True)
        )

        self.assertIn(recipient_org.id, recipient_ids)
        self.assertIn(recipient_person.id, recipient_ids)

    def test_eligible_correspondent_contacts_for_destination_returns_destination_contact(self):
        correspondent = self._create_person("Cora Correspondent")
        destination = self._create_destination("DLA", correspondent)

        correspondent_ids = set(
            eligible_correspondent_contacts_for_destination(destination).values_list(
                "id", flat=True
            )
        )

        self.assertEqual(correspondent_ids, {correspondent.id})

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
