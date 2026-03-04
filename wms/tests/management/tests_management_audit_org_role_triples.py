import csv
import tempfile

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from contacts.models import Contact, ContactType
from wms.models import (
    Destination,
    OrganizationRole,
    OrganizationRoleAssignment,
    RecipientBinding,
    ShipperScope,
    WmsRuntimeSettings,
)


class AuditOrgRoleTriplesCommandTests(TestCase):
    def _create_org(self, name: str) -> Contact:
        return Contact.objects.create(
            name=name,
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )

    def _create_destination(self, *, iata_code: str, correspondent: Contact) -> Destination:
        return Destination.objects.create(
            city=f"City {iata_code}",
            iata_code=iata_code,
            country="Country",
            correspondent_contact=correspondent,
            is_active=True,
        )

    def test_command_exports_accepted_and_refused_with_reason(self):
        runtime = WmsRuntimeSettings.get_solo()
        runtime.org_roles_engine_enabled = True
        runtime.save(update_fields=["org_roles_engine_enabled"])

        correspondent = self._create_org("Corr")
        destination = self._create_destination(iata_code="DLA", correspondent=correspondent)
        other_destination = self._create_destination(
            iata_code="ABJ",
            correspondent=correspondent,
        )

        shipper_ok = self._create_org("Shipper OK")
        shipper_bad_scope = self._create_org("Shipper Bad Scope")
        recipient_ok = self._create_org("Recipient OK")
        recipient_missing_binding = self._create_org("Recipient Missing")

        shipper_ok_assignment = OrganizationRoleAssignment.objects.create(
            organization=shipper_ok,
            role=OrganizationRole.SHIPPER,
            is_active=True,
        )
        shipper_bad_scope_assignment = OrganizationRoleAssignment.objects.create(
            organization=shipper_bad_scope,
            role=OrganizationRole.SHIPPER,
            is_active=True,
        )
        OrganizationRoleAssignment.objects.create(
            organization=recipient_ok,
            role=OrganizationRole.RECIPIENT,
            is_active=True,
        )
        OrganizationRoleAssignment.objects.create(
            organization=recipient_missing_binding,
            role=OrganizationRole.RECIPIENT,
            is_active=True,
        )

        ShipperScope.objects.create(
            role_assignment=shipper_ok_assignment,
            destination=destination,
            all_destinations=False,
            is_active=True,
        )
        ShipperScope.objects.create(
            role_assignment=shipper_bad_scope_assignment,
            destination=other_destination,
            all_destinations=False,
            is_active=True,
        )

        RecipientBinding.objects.create(
            shipper_org=shipper_ok,
            recipient_org=recipient_ok,
            destination=destination,
            is_active=True,
        )

        with tempfile.NamedTemporaryFile(suffix=".csv") as output_file:
            call_command(
                "audit_org_role_triples",
                output=output_file.name,
                progress_every=1000,
            )
            output_file.seek(0)
            rows = list(csv.DictReader(output_file.read().decode("utf-8").splitlines()))

        self.assertEqual(len(rows), 8)

        dla_rows = [row for row in rows if row["destination_iata"] == "DLA"]
        self.assertEqual(len(dla_rows), 4)

        accepted_rows = [row for row in dla_rows if row["status"] == "accepted"]
        self.assertEqual(len(accepted_rows), 1)
        self.assertEqual(accepted_rows[0]["shipper_org_name"], "Shipper OK")
        self.assertEqual(accepted_rows[0]["recipient_org_name"], "Recipient OK")

        refused_missing_binding = [
            row
            for row in dla_rows
            if row["status"] == "refused"
            and row["reason_code"] == "recipient_binding_missing"
        ]
        self.assertEqual(len(refused_missing_binding), 1)
        self.assertEqual(refused_missing_binding[0]["shipper_org_name"], "Shipper OK")
        self.assertEqual(
            refused_missing_binding[0]["recipient_org_name"],
            "Recipient Missing",
        )

        refused_out_of_scope = [
            row
            for row in dla_rows
            if row["status"] == "refused"
            and row["reason_code"] == "shipper_out_of_scope"
        ]
        self.assertEqual(len(refused_out_of_scope), 2)

    def test_command_fails_when_org_roles_engine_is_disabled(self):
        runtime = WmsRuntimeSettings.get_solo()
        runtime.org_roles_engine_enabled = False
        runtime.save(update_fields=["org_roles_engine_enabled"])

        with self.assertRaises(CommandError):
            call_command("audit_org_role_triples", output="docs/audits/should_not_exist.csv")
