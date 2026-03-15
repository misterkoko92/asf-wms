from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from contacts.models import Contact, ContactTag, ContactType
from wms.models import Destination, OrganizationRole, OrganizationRoleAssignment


class BackfillCorrespondentRecipientsCommandTests(TestCase):
    def setUp(self):
        self.correspondent_tag = ContactTag.objects.create(name="correspondant")

    def _attach_correspondent_tag_without_signal(self, contact):
        Contact.tags.through.objects.create(contact=contact, contacttag=self.correspondent_tag)

    def test_dry_run_reports_changes_without_persisting(self):
        person = Contact.objects.create(
            name="Dry Run Correspondent",
            contact_type=ContactType.PERSON,
            is_active=True,
        )
        self._attach_correspondent_tag_without_signal(person)

        stdout = StringIO()

        call_command("backfill_correspondent_recipients", "--dry-run", stdout=stdout)

        output = stdout.getvalue()
        self.assertIn("Backfill correspondent recipients [DRY RUN]", output)
        self.assertIn("- Correspondents scanned: 1", output)
        self.assertIn("- Support organizations created: 1", output)
        self.assertFalse(
            Contact.objects.filter(
                name="ASF - CORRESPONDANT",
                contact_type=ContactType.ORGANIZATION,
            ).exists()
        )
        person.refresh_from_db()
        self.assertIsNone(person.organization)
        self.assertFalse(person.tags.filter(name__iexact="destinataire").exists())
        self.assertFalse(
            OrganizationRoleAssignment.objects.filter(role=OrganizationRole.RECIPIENT).exists()
        )

    def test_apply_updates_existing_correspondents_and_reuses_shared_support_org(self):
        first = Contact.objects.create(
            name="First Backfill Correspondent",
            contact_type=ContactType.PERSON,
            is_active=True,
        )
        second = Contact.objects.create(
            name="Second Backfill Correspondent",
            contact_type=ContactType.PERSON,
            is_active=True,
        )
        self._attach_correspondent_tag_without_signal(first)
        self._attach_correspondent_tag_without_signal(second)

        stdout = StringIO()

        call_command("backfill_correspondent_recipients", "--apply", stdout=stdout)

        output = stdout.getvalue()
        self.assertIn("Backfill correspondent recipients [APPLY]", output)
        self.assertIn("- Correspondents scanned: 2", output)
        self.assertEqual(
            Contact.objects.filter(
                name="ASF - CORRESPONDANT",
                contact_type=ContactType.ORGANIZATION,
            ).count(),
            1,
        )
        support_org = Contact.objects.get(
            name="ASF - CORRESPONDANT",
            contact_type=ContactType.ORGANIZATION,
        )
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(first.organization, support_org)
        self.assertEqual(second.organization, support_org)
        self.assertTrue(first.tags.filter(name__iexact="destinataire").exists())
        self.assertTrue(second.tags.filter(name__iexact="destinataire").exists())
        self.assertTrue(
            OrganizationRoleAssignment.objects.filter(
                organization=support_org,
                role=OrganizationRole.RECIPIENT,
                is_active=True,
            ).exists()
        )

    def test_apply_syncs_correspondent_destination_scope_from_destination_reference(self):
        person = Contact.objects.create(
            name="Scoped Backfill Correspondent",
            contact_type=ContactType.PERSON,
            is_active=True,
        )
        self._attach_correspondent_tag_without_signal(person)
        destination = Destination.objects.create(
            city="Libreville",
            iata_code="LBV",
            country="Gabon",
            correspondent_contact=person,
            is_active=True,
        )

        call_command("backfill_correspondent_recipients", "--apply")

        person.refresh_from_db()
        self.assertEqual(
            set(person.destinations.values_list("id", flat=True)),
            {destination.id},
        )
        self.assertEqual(person.destination_id, destination.id)

        stdout = StringIO()
        call_command("backfill_correspondent_recipients", "--dry-run", stdout=stdout)
        output = stdout.getvalue()
        self.assertIn("- Contacts changed: 0", output)
