from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from contacts.correspondent_recipient_promotion import SUPPORT_ORGANIZATION_NAME
from contacts.models import Contact, ContactType
from wms.models import (
    Destination,
    OrganizationContact,
    OrganizationRole,
    OrganizationRoleAssignment,
    OrganizationRoleContact,
    RecipientBinding,
    ShipmentAuthorizedRecipientContact,
    ShipmentRecipientContact,
    ShipmentRecipientOrganization,
    ShipmentShipper,
    ShipmentShipperRecipientLink,
    ShipmentValidationStatus,
    ShipperScope,
)


class BackfillShipmentPartiesCommandTests(TestCase):
    def _create_organization(self, name: str) -> Contact:
        return Contact.objects.create(
            name=name,
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )

    def _create_person(
        self,
        *,
        first_name: str,
        last_name: str,
        organization: Contact | None = None,
        is_active: bool = True,
    ) -> Contact:
        return Contact.objects.create(
            name=f"{first_name} {last_name}",
            contact_type=ContactType.PERSON,
            first_name=first_name,
            last_name=last_name,
            organization=organization,
            is_active=is_active,
        )

    def _create_destination(
        self,
        iata_code: str,
        *,
        correspondent_contact: Contact | None = None,
    ) -> Destination:
        if correspondent_contact is None:
            correspondent_contact = self._create_organization(f"Correspondent {iata_code}")
        return Destination.objects.create(
            city=f"City {iata_code}",
            iata_code=iata_code,
            country="Country",
            correspondent_contact=correspondent_contact,
            is_active=True,
        )

    def _create_role_assignment(
        self,
        *,
        organization: Contact,
        role: str,
        is_active: bool = True,
    ) -> OrganizationRoleAssignment:
        return OrganizationRoleAssignment.objects.create(
            organization=organization,
            role=role,
            is_active=is_active,
        )

    def _create_role_contact(
        self,
        *,
        role_assignment: OrganizationRoleAssignment,
        first_name: str,
        last_name: str,
        email: str,
        is_primary: bool = False,
        is_active: bool = True,
    ) -> OrganizationContact:
        organization_contact = OrganizationContact.objects.create(
            organization=role_assignment.organization,
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone="0102030405",
            is_active=is_active,
        )
        OrganizationRoleContact.objects.create(
            role_assignment=role_assignment,
            contact=organization_contact,
            is_primary=is_primary,
            is_active=is_active,
        )
        return organization_contact

    def test_apply_backfill_creates_shipper_from_global_scope(self):
        shipper_org = self._create_organization("Aviation Sans Frontieres")
        shipper_assignment = self._create_role_assignment(
            organization=shipper_org,
            role=OrganizationRole.SHIPPER,
        )
        self._create_role_contact(
            role_assignment=shipper_assignment,
            first_name="Alice",
            last_name="Global",
            email="alice.global@example.org",
            is_primary=True,
        )
        ShipperScope.objects.create(
            role_assignment=shipper_assignment,
            all_destinations=True,
            is_active=True,
        )

        call_command("backfill_shipment_parties_from_org_roles", "--apply")

        shipper = ShipmentShipper.objects.get(organization=shipper_org)
        self.assertTrue(shipper.can_send_to_all)
        self.assertEqual(shipper.validation_status, ShipmentValidationStatus.VALIDATED)
        self.assertTrue(shipper.default_contact.is_active)
        self.assertEqual(shipper.default_contact.organization, shipper_org)

    def test_apply_backfill_creates_shared_recipient_structure_and_authorized_contacts(self):
        destination = self._create_destination("BKO")

        shipper_one_org = self._create_organization("ASF")
        shipper_one_assignment = self._create_role_assignment(
            organization=shipper_one_org,
            role=OrganizationRole.SHIPPER,
        )
        self._create_role_contact(
            role_assignment=shipper_one_assignment,
            first_name="Jean",
            last_name="ShipperOne",
            email="shipper.one@example.org",
            is_primary=True,
        )
        ShipperScope.objects.create(
            role_assignment=shipper_one_assignment,
            all_destinations=False,
            destination=destination,
            is_active=True,
        )

        shipper_two_org = self._create_organization("MSF")
        shipper_two_assignment = self._create_role_assignment(
            organization=shipper_two_org,
            role=OrganizationRole.SHIPPER,
        )
        self._create_role_contact(
            role_assignment=shipper_two_assignment,
            first_name="Marie",
            last_name="ShipperTwo",
            email="shipper.two@example.org",
            is_primary=True,
        )
        ShipperScope.objects.create(
            role_assignment=shipper_two_assignment,
            all_destinations=False,
            destination=destination,
            is_active=True,
        )

        recipient_org = self._create_organization("Hopital Bamako")
        recipient_assignment = self._create_role_assignment(
            organization=recipient_org,
            role=OrganizationRole.RECIPIENT,
        )
        self._create_role_contact(
            role_assignment=recipient_assignment,
            first_name="Docteur",
            last_name="Truc",
            email="truc@example.org",
            is_primary=True,
        )
        self._create_role_contact(
            role_assignment=recipient_assignment,
            first_name="Docteur",
            last_name="Machin",
            email="machin@example.org",
            is_primary=False,
        )

        RecipientBinding.objects.create(
            shipper_org=shipper_one_org,
            recipient_org=recipient_org,
            destination=destination,
            is_active=True,
        )
        RecipientBinding.objects.create(
            shipper_org=shipper_two_org,
            recipient_org=recipient_org,
            destination=destination,
            is_active=True,
        )

        stdout = StringIO()
        call_command("backfill_shipment_parties_from_org_roles", "--apply", stdout=stdout)

        output = stdout.getvalue()
        self.assertIn("Backfill shipment parties from org roles [APPLY]", output)
        self.assertIn("- Shippers created: 2", output)

        shipment_recipient = ShipmentRecipientOrganization.objects.get(organization=recipient_org)
        self.assertEqual(shipment_recipient.destination, destination)
        self.assertEqual(shipment_recipient.validation_status, ShipmentValidationStatus.VALIDATED)
        self.assertFalse(shipment_recipient.is_correspondent)

        recipient_contacts = ShipmentRecipientContact.objects.filter(
            recipient_organization=shipment_recipient
        ).order_by("contact__last_name")
        self.assertEqual(recipient_contacts.count(), 2)

        shipper_links = ShipmentShipperRecipientLink.objects.filter(
            recipient_organization=shipment_recipient
        ).order_by("shipper__organization__name")
        self.assertEqual(shipper_links.count(), 2)

        for link in shipper_links:
            self.assertEqual(
                ShipmentAuthorizedRecipientContact.objects.filter(link=link).count(),
                2,
            )
            default_authorized = ShipmentAuthorizedRecipientContact.objects.get(
                link=link,
                is_default=True,
            )
            self.assertEqual(default_authorized.recipient_contact.contact.last_name, "Truc")

    def test_apply_backfill_creates_stopover_correspondent_without_legacy_recipient_role(self):
        correspondent = self._create_person(
            first_name="Paul",
            last_name="Correspondent",
        )
        destination = self._create_destination(
            "DLA",
            correspondent_contact=correspondent,
        )

        call_command("backfill_shipment_parties_from_org_roles", "--apply")

        support_org = Contact.objects.get(
            name=SUPPORT_ORGANIZATION_NAME,
            contact_type=ContactType.ORGANIZATION,
        )
        correspondent.refresh_from_db()
        self.assertEqual(correspondent.organization, support_org)

        shipment_recipient = ShipmentRecipientOrganization.objects.get(
            organization=support_org,
            destination=destination,
        )
        self.assertTrue(shipment_recipient.is_correspondent)
        self.assertEqual(
            ShipmentRecipientContact.objects.get(
                recipient_organization=shipment_recipient,
                contact=correspondent,
            ).contact,
            correspondent,
        )
        self.assertFalse(
            OrganizationRoleAssignment.objects.filter(
                organization=support_org,
                role=OrganizationRole.RECIPIENT,
            ).exists()
        )

    def test_dry_run_reports_without_persisting(self):
        destination = self._create_destination("CMN")
        shipper_org = self._create_organization("Dry Run Shipper")
        shipper_assignment = self._create_role_assignment(
            organization=shipper_org,
            role=OrganizationRole.SHIPPER,
        )
        self._create_role_contact(
            role_assignment=shipper_assignment,
            first_name="Dry",
            last_name="Run",
            email="dry.run@example.org",
            is_primary=True,
        )
        ShipperScope.objects.create(
            role_assignment=shipper_assignment,
            all_destinations=False,
            destination=destination,
            is_active=True,
        )

        recipient_org = self._create_organization("Dry Run Recipient")
        recipient_assignment = self._create_role_assignment(
            organization=recipient_org,
            role=OrganizationRole.RECIPIENT,
        )
        self._create_role_contact(
            role_assignment=recipient_assignment,
            first_name="Recipient",
            last_name="DryRun",
            email="recipient.dry.run@example.org",
            is_primary=True,
        )
        RecipientBinding.objects.create(
            shipper_org=shipper_org,
            recipient_org=recipient_org,
            destination=destination,
            is_active=True,
        )

        stdout = StringIO()
        call_command("backfill_shipment_parties_from_org_roles", "--dry-run", stdout=stdout)

        output = stdout.getvalue()
        self.assertIn("Backfill shipment parties from org roles [DRY RUN]", output)
        self.assertIn("- Shippers created: 1", output)
        self.assertIn("- Correspondent recipient organizations created:", output)
        self.assertEqual(ShipmentShipper.objects.count(), 0)
        self.assertEqual(ShipmentRecipientOrganization.objects.count(), 0)
        self.assertEqual(ShipmentShipperRecipientLink.objects.count(), 0)
