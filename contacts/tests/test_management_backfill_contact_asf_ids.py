from io import StringIO
from types import SimpleNamespace
from unittest import mock

from django.core.management import call_command
from django.test import TestCase

from contacts.models import Contact, ContactType


class BackfillContactAsfIdsCommandTests(TestCase):
    def test_dry_run_reports_missing_contacts_without_persisting(self):
        legacy_org = Contact.objects.create(
            name="Legacy Org",
            contact_type=ContactType.ORGANIZATION,
        )
        inactive_person = Contact.objects.create(
            contact_type=ContactType.PERSON,
            first_name="Inactive",
            last_name="Legacy",
            is_active=False,
        )
        preserved = Contact.objects.create(
            name="Preserved Org",
            contact_type=ContactType.ORGANIZATION,
            asf_id="ASF-MANUAL-01",
        )
        Contact.objects.filter(pk=legacy_org.pk).update(asf_id=None)
        Contact.objects.filter(pk=inactive_person.pk).update(asf_id="")

        stdout = StringIO()

        call_command("backfill_contact_asf_ids", "--dry-run", stdout=stdout)

        output = stdout.getvalue()
        self.assertIn("Backfill contact asf ids [DRY RUN]", output)
        self.assertIn("- Contacts scanned: 3", output)
        self.assertIn("- Contacts missing asf_id: 2", output)
        self.assertIn("- Contacts backfilled: 2", output)
        legacy_org.refresh_from_db()
        inactive_person.refresh_from_db()
        preserved.refresh_from_db()
        self.assertIsNone(legacy_org.asf_id)
        self.assertEqual(inactive_person.asf_id, "")
        self.assertEqual(preserved.asf_id, "ASF-MANUAL-01")

    def test_apply_backfills_all_missing_contacts_and_is_idempotent(self):
        legacy_org = Contact.objects.create(
            name="Legacy Org",
            contact_type=ContactType.ORGANIZATION,
        )
        inactive_person = Contact.objects.create(
            contact_type=ContactType.PERSON,
            first_name="Inactive",
            last_name="Legacy",
            is_active=False,
        )
        preserved = Contact.objects.create(
            name="Preserved Org",
            contact_type=ContactType.ORGANIZATION,
            asf_id="ASF-MANUAL-01",
        )
        Contact.objects.filter(pk=legacy_org.pk).update(asf_id=None)
        Contact.objects.filter(pk=inactive_person.pk).update(asf_id="")

        stdout = StringIO()

        call_command("backfill_contact_asf_ids", "--apply", stdout=stdout)

        output = stdout.getvalue()
        self.assertIn("Backfill contact asf ids [APPLY]", output)
        self.assertIn("- Contacts scanned: 3", output)
        self.assertIn("- Contacts missing asf_id: 2", output)
        self.assertIn("- Contacts backfilled: 2", output)
        legacy_org.refresh_from_db()
        inactive_person.refresh_from_db()
        preserved.refresh_from_db()
        self.assertEqual(legacy_org.asf_id, f"ASF-C-{legacy_org.pk:08d}")
        self.assertEqual(inactive_person.asf_id, f"ASF-C-{inactive_person.pk:08d}")
        self.assertEqual(preserved.asf_id, "ASF-MANUAL-01")

        second_stdout = StringIO()
        call_command("backfill_contact_asf_ids", "--apply", stdout=second_stdout)
        second_output = second_stdout.getvalue()
        self.assertIn("- Contacts missing asf_id: 0", second_output)
        self.assertIn("- Contacts backfilled: 0", second_output)

    def test_apply_backfills_missing_contacts_with_installation_reference_prefix(self):
        legacy_org = Contact.objects.create(
            name="Legacy Client Org",
            contact_type=ContactType.ORGANIZATION,
        )
        preserved = Contact.objects.create(
            name="Preserved Client Org",
            contact_type=ContactType.ORGANIZATION,
            asf_id="LEGACY-XYZ-42",
        )
        Contact.objects.filter(pk=legacy_org.pk).update(asf_id=None)
        installation = SimpleNamespace(
            references=SimpleNamespace(contact_identifier_generated_prefix="FBN-C")
        )
        stdout = StringIO()

        with mock.patch(
            "contacts.asf_ids.get_installation_config",
            return_value=installation,
        ):
            call_command("backfill_contact_asf_ids", "--apply", stdout=stdout)

        legacy_org.refresh_from_db()
        preserved.refresh_from_db()
        self.assertEqual(legacy_org.asf_id, f"FBN-C-{legacy_org.pk:08d}")
        self.assertEqual(preserved.asf_id, "LEGACY-XYZ-42")
