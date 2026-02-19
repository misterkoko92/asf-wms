from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from contacts.models import Contact, ContactType
from wms.models import Destination


class AuditContactDestinationsCommandTests(TestCase):
    def _create_destination(self, *, suffix):
        correspondent = Contact.objects.create(
            name=f"Correspondant {suffix}",
            contact_type=ContactType.PERSON,
            is_active=True,
        )
        return Destination.objects.create(
            city=f"City {suffix}",
            iata_code=f"D{suffix:03d}",
            country="France",
            correspondent_contact=correspondent,
            is_active=True,
        )

    def test_command_reports_no_issue_when_scope_is_consistent(self):
        destination = self._create_destination(suffix=1)
        contact = Contact.objects.create(
            name="Consistent",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
            destination=destination,
        )
        contact.destinations.add(destination)

        stdout = StringIO()
        call_command("audit_contact_destinations", stdout=stdout)

        output = stdout.getvalue()
        self.assertIn("Aucune incohérence détectée", output)

    def test_command_detects_and_applies_fixes(self):
        destination_a = self._create_destination(suffix=2)
        destination_b = self._create_destination(suffix=3)

        legacy_only = Contact.objects.create(
            name="Legacy only",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
            destination=destination_a,
        )
        single_mismatch = Contact.objects.create(
            name="Single mismatch",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
            destination=destination_a,
        )
        single_mismatch.destinations.add(destination_b)
        legacy_with_multi = Contact.objects.create(
            name="Legacy multi",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
            destination=destination_a,
        )
        legacy_with_multi.destinations.add(destination_a, destination_b)

        with self.assertRaises(CommandError):
            call_command("audit_contact_destinations", fail_on_issues=True)

        stdout = StringIO()
        call_command("audit_contact_destinations", apply=True, stdout=stdout)
        output = stdout.getvalue()
        self.assertIn("corrigée(s)", output)

        legacy_only.refresh_from_db()
        single_mismatch.refresh_from_db()
        legacy_with_multi.refresh_from_db()
        self.assertEqual(
            list(legacy_only.destinations.values_list("id", flat=True)),
            [destination_a.id],
        )
        self.assertEqual(legacy_only.destination_id, destination_a.id)
        self.assertEqual(single_mismatch.destination_id, destination_b.id)
        self.assertIsNone(legacy_with_multi.destination_id)
