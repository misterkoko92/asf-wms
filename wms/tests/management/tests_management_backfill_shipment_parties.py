from io import StringIO
from unittest.mock import patch

from django.core.management import CommandError, call_command
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

    def test_apply_backfill_ignores_binding_shipper_without_active_scope(self):
        destination = self._create_destination("NOS")

        shipper_org = self._create_organization("Unscoped Shipper")
        shipper_assignment = self._create_role_assignment(
            organization=shipper_org,
            role=OrganizationRole.SHIPPER,
        )
        self._create_role_contact(
            role_assignment=shipper_assignment,
            first_name="No",
            last_name="Scope",
            email="no.scope@example.org",
            is_primary=True,
        )

        recipient_org = self._create_organization("Scoped Recipient")
        recipient_assignment = self._create_role_assignment(
            organization=recipient_org,
            role=OrganizationRole.RECIPIENT,
        )
        self._create_role_contact(
            role_assignment=recipient_assignment,
            first_name="Scoped",
            last_name="Recipient",
            email="scoped.recipient@example.org",
            is_primary=True,
        )
        RecipientBinding.objects.create(
            shipper_org=shipper_org,
            recipient_org=recipient_org,
            destination=destination,
            is_active=True,
        )

        call_command("backfill_shipment_parties_from_org_roles", "--apply")

        self.assertFalse(ShipmentShipper.objects.filter(organization=shipper_org).exists())
        self.assertFalse(
            ShipmentShipperRecipientLink.objects.filter(
                shipper__organization=shipper_org,
                recipient_organization__organization=recipient_org,
            ).exists()
        )

    def test_apply_backfill_reassigns_single_default_authorized_contact_on_rerun(self):
        destination = self._create_destination("GAO")
        shipper_org = self._create_organization("ASF Rerun")
        shipper_assignment = self._create_role_assignment(
            organization=shipper_org,
            role=OrganizationRole.SHIPPER,
        )
        self._create_role_contact(
            role_assignment=shipper_assignment,
            first_name="Jeanne",
            last_name="Shipper",
            email="rerun.shipper@example.org",
            is_primary=True,
        )
        ShipperScope.objects.create(
            role_assignment=shipper_assignment,
            all_destinations=False,
            destination=destination,
            is_active=True,
        )

        recipient_org = self._create_organization("Hopital Gao")
        recipient_assignment = self._create_role_assignment(
            organization=recipient_org,
            role=OrganizationRole.RECIPIENT,
        )
        primary_contact = self._create_role_contact(
            role_assignment=recipient_assignment,
            first_name="Docteur",
            last_name="Alpha",
            email="alpha@example.org",
            is_primary=True,
        )
        secondary_contact = self._create_role_contact(
            role_assignment=recipient_assignment,
            first_name="Docteur",
            last_name="Beta",
            email="beta@example.org",
            is_primary=False,
        )
        RecipientBinding.objects.create(
            shipper_org=shipper_org,
            recipient_org=recipient_org,
            destination=destination,
            is_active=True,
        )

        call_command("backfill_shipment_parties_from_org_roles", "--apply")

        primary_role_contact = recipient_assignment.role_contacts.get(contact=primary_contact)
        secondary_role_contact = recipient_assignment.role_contacts.get(contact=secondary_contact)
        primary_role_contact.is_primary = False
        primary_role_contact.save(update_fields=["is_primary"])
        secondary_role_contact.is_primary = True
        secondary_role_contact.save(update_fields=["is_primary"])

        call_command("backfill_shipment_parties_from_org_roles", "--apply")

        link = ShipmentShipperRecipientLink.objects.get(
            shipper__organization=shipper_org,
            recipient_organization__organization=recipient_org,
        )
        self.assertEqual(
            ShipmentAuthorizedRecipientContact.objects.filter(
                link=link,
                is_default=True,
            ).count(),
            1,
        )
        self.assertEqual(
            ShipmentAuthorizedRecipientContact.objects.get(
                link=link,
                is_default=True,
            ).recipient_contact.contact.last_name,
            "Beta",
        )

    def test_apply_backfill_repairs_inactive_existing_target_row(self):
        destination_one = self._create_destination("KGL")
        destination_two = self._create_destination("FIH")

        shipper_org = self._create_organization("Repair Shipper")
        shipper_assignment = self._create_role_assignment(
            organization=shipper_org,
            role=OrganizationRole.SHIPPER,
        )
        self._create_role_contact(
            role_assignment=shipper_assignment,
            first_name="Repair",
            last_name="Shipper",
            email="repair.shipper@example.org",
            is_primary=True,
        )
        ShipperScope.objects.create(
            role_assignment=shipper_assignment,
            all_destinations=False,
            destination=destination_two,
            is_active=True,
        )

        recipient_org = self._create_organization("Repair Recipient")
        stale_target = ShipmentRecipientOrganization.objects.create(
            organization=recipient_org,
            destination=destination_one,
            validation_status=ShipmentValidationStatus.VALIDATED,
            is_correspondent=False,
            is_active=False,
        )
        recipient_assignment = self._create_role_assignment(
            organization=recipient_org,
            role=OrganizationRole.RECIPIENT,
        )
        self._create_role_contact(
            role_assignment=recipient_assignment,
            first_name="Repair",
            last_name="Recipient",
            email="repair.recipient@example.org",
            is_primary=True,
        )
        RecipientBinding.objects.create(
            shipper_org=shipper_org,
            recipient_org=recipient_org,
            destination=destination_two,
            is_active=True,
        )

        call_command("backfill_shipment_parties_from_org_roles", "--apply")

        stale_target.refresh_from_db()
        self.assertEqual(stale_target.destination, destination_two)
        self.assertTrue(stale_target.is_active)

    def test_apply_backfill_deactivates_removed_recipient_contacts_on_rerun(self):
        destination = self._create_destination("NBO")
        shipper_org = self._create_organization("ASF Cleanup")
        shipper_assignment = self._create_role_assignment(
            organization=shipper_org,
            role=OrganizationRole.SHIPPER,
        )
        self._create_role_contact(
            role_assignment=shipper_assignment,
            first_name="Cleanup",
            last_name="Shipper",
            email="cleanup.shipper@example.org",
            is_primary=True,
        )
        ShipperScope.objects.create(
            role_assignment=shipper_assignment,
            all_destinations=False,
            destination=destination,
            is_active=True,
        )

        recipient_org = self._create_organization("Cleanup Recipient")
        recipient_assignment = self._create_role_assignment(
            organization=recipient_org,
            role=OrganizationRole.RECIPIENT,
        )
        primary_contact = self._create_role_contact(
            role_assignment=recipient_assignment,
            first_name="Active",
            last_name="One",
            email="active.one@example.org",
            is_primary=True,
        )
        stale_contact = self._create_role_contact(
            role_assignment=recipient_assignment,
            first_name="Stale",
            last_name="Two",
            email="stale.two@example.org",
            is_primary=False,
        )
        RecipientBinding.objects.create(
            shipper_org=shipper_org,
            recipient_org=recipient_org,
            destination=destination,
            is_active=True,
        )

        call_command("backfill_shipment_parties_from_org_roles", "--apply")

        stale_role_contact = recipient_assignment.role_contacts.get(contact=stale_contact)
        stale_role_contact.is_active = False
        stale_role_contact.save(update_fields=["is_active"])
        primary_role_contact = recipient_assignment.role_contacts.get(contact=primary_contact)
        primary_role_contact.is_primary = True
        primary_role_contact.save(update_fields=["is_primary"])

        call_command("backfill_shipment_parties_from_org_roles", "--apply")

        link = ShipmentShipperRecipientLink.objects.get(
            shipper__organization=shipper_org,
            recipient_organization__organization=recipient_org,
        )
        stale_recipient_contact = ShipmentRecipientContact.objects.get(
            recipient_organization__organization=recipient_org,
            contact__email="stale.two@example.org",
        )
        self.assertFalse(stale_recipient_contact.is_active)
        stale_authorized = ShipmentAuthorizedRecipientContact.objects.get(
            link=link,
            recipient_contact=stale_recipient_contact,
        )
        self.assertFalse(stale_authorized.is_active)
        self.assertFalse(stale_authorized.is_default)

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

    def test_apply_backfill_rolls_back_apply_mode_on_late_failure(self):
        destination = self._create_destination("RBK")
        shipper_org = self._create_organization("Rollback Shipper")
        shipper_assignment = self._create_role_assignment(
            organization=shipper_org,
            role=OrganizationRole.SHIPPER,
        )
        self._create_role_contact(
            role_assignment=shipper_assignment,
            first_name="Rollback",
            last_name="Owner",
            email="rollback@example.org",
            is_primary=True,
        )
        ShipperScope.objects.create(
            role_assignment=shipper_assignment,
            all_destinations=False,
            destination=destination,
            is_active=True,
        )

        with patch(
            "wms.management.commands.backfill_shipment_parties_from_org_roles."
            "ShipmentPartyBackfillService._backfill_recipient_bindings",
            side_effect=CommandError("boom"),
        ):
            with self.assertRaisesMessage(CommandError, "boom"):
                call_command("backfill_shipment_parties_from_org_roles", "--apply")

        self.assertEqual(ShipmentShipper.objects.count(), 0)
        self.assertEqual(ShipmentRecipientOrganization.objects.count(), 0)

    def test_apply_backfill_skips_recipient_conflicts_and_continues(self):
        destination_one = self._create_destination("NIM")
        destination_two = self._create_destination("MRS")

        shipper_org = self._create_organization("ASF Multi")
        shipper_assignment = self._create_role_assignment(
            organization=shipper_org,
            role=OrganizationRole.SHIPPER,
        )
        self._create_role_contact(
            role_assignment=shipper_assignment,
            first_name="Camille",
            last_name="Shipper",
            email="multi.shipper@example.org",
            is_primary=True,
        )
        ShipperScope.objects.create(
            role_assignment=shipper_assignment,
            all_destinations=False,
            destination=destination_one,
            is_active=True,
        )
        ShipperScope.objects.create(
            role_assignment=shipper_assignment,
            all_destinations=False,
            destination=destination_two,
            is_active=True,
        )

        recipient_org = self._create_organization("Hopital Multi")
        recipient_assignment = self._create_role_assignment(
            organization=recipient_org,
            role=OrganizationRole.RECIPIENT,
        )
        self._create_role_contact(
            role_assignment=recipient_assignment,
            first_name="Docteur",
            last_name="Unique",
            email="multi.recipient@example.org",
            is_primary=True,
        )
        RecipientBinding.objects.create(
            shipper_org=shipper_org,
            recipient_org=recipient_org,
            destination=destination_one,
            is_active=True,
        )
        RecipientBinding.objects.create(
            shipper_org=shipper_org,
            recipient_org=recipient_org,
            destination=destination_two,
            is_active=True,
        )

        stdout = StringIO()
        call_command("backfill_shipment_parties_from_org_roles", "--apply", stdout=stdout)

        output = stdout.getvalue()
        self.assertIn("- Conflicting recipient targets: 1", output)
        self.assertIn("- Recipient bindings skipped: 2", output)
        self.assertTrue(ShipmentShipper.objects.filter(organization=shipper_org).exists())
        self.assertFalse(
            ShipmentRecipientOrganization.objects.filter(organization=recipient_org).exists()
        )

    def test_apply_backfill_skips_support_correspondent_conflicts(self):
        self._create_destination(
            "LBV",
            correspondent_contact=self._create_person(
                first_name="Paul",
                last_name="Libreville",
            ),
        )
        self._create_destination(
            "NDJ",
            correspondent_contact=self._create_person(
                first_name="Marie",
                last_name="Ndjamena",
            ),
        )

        stdout = StringIO()
        call_command("backfill_shipment_parties_from_org_roles", "--apply", stdout=stdout)

        output = stdout.getvalue()
        self.assertIn("- Conflicting recipient targets: 1", output)
        self.assertIn("- Correspondent destinations skipped: 2", output)
        self.assertFalse(
            Contact.objects.filter(
                name=SUPPORT_ORGANIZATION_NAME,
                contact_type=ContactType.ORGANIZATION,
            ).exists()
        )

    def test_apply_backfill_reuses_inactive_correspondent_organization(self):
        inactive_org = self._create_organization("Dormant Correspondent Org")
        inactive_org.is_active = False
        inactive_org.save(update_fields=["is_active"])
        correspondent = self._create_person(
            first_name="Claire",
            last_name="Dormant",
            organization=inactive_org,
        )
        destination = self._create_destination(
            "ABJ",
            correspondent_contact=correspondent,
        )

        call_command("backfill_shipment_parties_from_org_roles", "--apply")

        inactive_org.refresh_from_db()
        self.assertTrue(inactive_org.is_active)
        shipment_recipient = ShipmentRecipientOrganization.objects.get(
            organization=inactive_org,
            destination=destination,
        )
        self.assertTrue(shipment_recipient.is_correspondent)
        self.assertFalse(
            Contact.objects.filter(
                name=SUPPORT_ORGANIZATION_NAME,
                contact_type=ContactType.ORGANIZATION,
            ).exists()
        )

    def test_apply_backfill_skips_source_conflict_against_existing_target_data(self):
        destination_one = self._create_destination("TGT")
        destination_two = self._create_destination("SRC")
        shipper_org = self._create_organization("Existing Target Shipper")
        shipper_assignment = self._create_role_assignment(
            organization=shipper_org,
            role=OrganizationRole.SHIPPER,
        )
        self._create_role_contact(
            role_assignment=shipper_assignment,
            first_name="Existing",
            last_name="Target",
            email="existing.target@example.org",
            is_primary=True,
        )
        ShipperScope.objects.create(
            role_assignment=shipper_assignment,
            all_destinations=False,
            destination=destination_two,
            is_active=True,
        )

        recipient_org = self._create_organization("Existing Target Recipient")
        ShipmentRecipientOrganization.objects.create(
            organization=recipient_org,
            destination=destination_one,
            validation_status=ShipmentValidationStatus.VALIDATED,
            is_correspondent=False,
            is_active=True,
        )
        recipient_assignment = self._create_role_assignment(
            organization=recipient_org,
            role=OrganizationRole.RECIPIENT,
        )
        self._create_role_contact(
            role_assignment=recipient_assignment,
            first_name="Target",
            last_name="Recipient",
            email="target.recipient@example.org",
            is_primary=True,
        )
        RecipientBinding.objects.create(
            shipper_org=shipper_org,
            recipient_org=recipient_org,
            destination=destination_two,
            is_active=True,
        )

        stdout = StringIO()
        call_command("backfill_shipment_parties_from_org_roles", "--apply", stdout=stdout)

        output = stdout.getvalue()
        self.assertIn("- Conflicting recipient targets: 1", output)
        self.assertIn("- Recipient bindings skipped: 1", output)
        self.assertEqual(
            ShipmentRecipientOrganization.objects.get(organization=recipient_org).destination,
            destination_one,
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
