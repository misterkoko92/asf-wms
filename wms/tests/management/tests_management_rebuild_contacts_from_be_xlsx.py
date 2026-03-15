from __future__ import annotations

import tempfile
from io import StringIO
from pathlib import Path

from django.core.management import call_command
from django.test import TestCase
from openpyxl import Workbook

from contacts.models import Contact, ContactTag, ContactType
from wms.contact_rebuild import (
    BeContactDataset,
    apply_be_contact_dataset,
    build_be_contact_dataset,
    render_review_report,
)
from wms.models import Destination, OrganizationRole, OrganizationRoleAssignment, RecipientBinding


class BeWorkbookMixin:
    HEADER = [
        "BE_DONATEUR",
        "ASSOCIATION_NOM",
        "ASSOCIATION_PAYS",
        "DESTINATAIRE_STRUCTURE",
        "DESTINATAIRE_STATUT",
        "CORRESPONDANT_PRENOM",
        "CORRESPONDANT_NOM",
        "CORRESPONDANT_PAYS",
        "BE_DESTINATION",
        "BE_CODE_IATA",
    ]

    def _build_be_workbook(self, rows: list[dict]) -> Path:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        path = Path(temp_dir.name) / "be_source.xlsx"

        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Sheet1"
        sheet.append(self.HEADER)
        for row in rows:
            sheet.append([row.get(header, "") for header in self.HEADER])
        workbook.save(path)
        return path


class RebuildContactsFromBeXlsxNormalizationTests(BeWorkbookMixin, TestCase):
    def test_build_be_contact_dataset_groups_entities_and_surfaces_no_ambiguity(self):
        workbook_path = self._build_be_workbook(
            [
                {
                    "BE_DONATEUR": "Homeperf Clamart",
                    "ASSOCIATION_NOM": "AVIATION SANS FRONTIERES",
                    "ASSOCIATION_PAYS": "France",
                    "DESTINATAIRE_STRUCTURE": "Recipient A",
                    "DESTINATAIRE_STATUT": "actif",
                    "CORRESPONDANT_PRENOM": "Leontine",
                    "CORRESPONDANT_NOM": "Rahazania",
                    "CORRESPONDANT_PAYS": "Madagascar",
                    "BE_DESTINATION": "ANTANANARIVO",
                    "BE_CODE_IATA": "TNR",
                },
                {
                    "ASSOCIATION_NOM": "Aviation Sans Frontieres",
                    "ASSOCIATION_PAYS": "France",
                    "DESTINATAIRE_STRUCTURE": "Recipient A",
                    "DESTINATAIRE_STATUT": "actif",
                    "CORRESPONDANT_PRENOM": "Leontine",
                    "CORRESPONDANT_NOM": "Rahazania",
                    "CORRESPONDANT_PAYS": "Madagascar",
                    "BE_DESTINATION": "ANTANANARIVO",
                    "BE_CODE_IATA": "TNR",
                },
            ]
        )

        dataset = build_be_contact_dataset(workbook_path)

        self.assertEqual(len(dataset.donors), 1)
        self.assertEqual(len(dataset.shippers), 1)
        self.assertEqual(len(dataset.recipients), 1)
        self.assertEqual(len(dataset.correspondents), 1)
        self.assertEqual(len(dataset.destinations), 1)
        self.assertEqual(
            dataset.recipient_bindings,
            [
                {
                    "recipient_key": "recipient a",
                    "shipper_key": "aviation sans frontieres",
                    "destination_iata": "TNR",
                }
            ],
        )
        self.assertEqual(dataset.review_items, [])

    def test_build_be_contact_dataset_reports_conflicting_shipper_data(self):
        workbook_path = self._build_be_workbook(
            [
                {
                    "ASSOCIATION_NOM": "Association Test",
                    "ASSOCIATION_PAYS": "France",
                    "DESTINATAIRE_STRUCTURE": "Recipient A",
                    "DESTINATAIRE_STATUT": "actif",
                    "CORRESPONDANT_PRENOM": "Marie",
                    "CORRESPONDANT_NOM": "Durand",
                    "CORRESPONDANT_PAYS": "Senegal",
                    "BE_DESTINATION": "DAKAR",
                    "BE_CODE_IATA": "DKR",
                },
                {
                    "ASSOCIATION_NOM": "association test",
                    "ASSOCIATION_PAYS": "Belgique",
                    "DESTINATAIRE_STRUCTURE": "Recipient B",
                    "DESTINATAIRE_STATUT": "actif",
                    "CORRESPONDANT_PRENOM": "Marie",
                    "CORRESPONDANT_NOM": "Durand",
                    "CORRESPONDANT_PAYS": "Senegal",
                    "BE_DESTINATION": "DAKAR",
                    "BE_CODE_IATA": "DKR",
                },
            ]
        )

        dataset = build_be_contact_dataset(workbook_path)

        self.assertEqual(len(dataset.review_items), 1)
        self.assertIn("conflicting", dataset.review_items[0]["reason"])
        report = render_review_report(dataset.review_items)
        self.assertIn("Association Test", report)
        self.assertIn("conflicting shipper country", report)


class RebuildContactsFromBeXlsxPersistenceTests(TestCase):
    def test_apply_be_contact_dataset_creates_contacts_destinations_and_org_role_links(self):
        dataset = BeContactDataset(
            donors=[{"key": "donor a", "name": "Donor A"}],
            shippers=[
                {
                    "key": "aviation sans frontieres",
                    "name": "AVIATION SANS FRONTIERES",
                    "country": "France",
                }
            ],
            recipients=[{"key": "recipient a", "name": "Recipient A", "status": "actif"}],
            correspondents=[
                {
                    "key": "leontine rahazania",
                    "name": "Leontine Rahazania",
                    "country": "Madagascar",
                }
            ],
            destinations=[
                {
                    "key": "TNR",
                    "city": "ANTANANARIVO",
                    "country": "Madagascar",
                    "iata_code": "TNR",
                    "correspondent_key": "leontine rahazania",
                }
            ],
            shipper_scopes=[
                {
                    "shipper_key": "aviation sans frontieres",
                    "destination_iata": "TNR",
                }
            ],
            recipient_bindings=[
                {
                    "recipient_key": "recipient a",
                    "shipper_key": "aviation sans frontieres",
                    "destination_iata": "TNR",
                }
            ],
            review_items=[],
        )

        apply_be_contact_dataset(dataset)

        shipper = Contact.objects.get(name="AVIATION SANS FRONTIERES")
        recipient = Contact.objects.get(name="Recipient A")
        correspondent = Contact.objects.get(name="Leontine Rahazania")
        destination = Destination.objects.get(iata_code="TNR")

        self.assertEqual(shipper.contact_type, ContactType.ORGANIZATION)
        self.assertEqual(recipient.contact_type, ContactType.ORGANIZATION)
        self.assertEqual(correspondent.contact_type, ContactType.PERSON)
        self.assertTrue(recipient.linked_shippers.filter(pk=shipper.pk).exists())
        self.assertEqual(destination.correspondent_contact_id, correspondent.id)
        self.assertTrue(
            OrganizationRoleAssignment.objects.filter(
                organization=shipper,
                role=OrganizationRole.SHIPPER,
                is_active=True,
            ).exists()
        )
        self.assertTrue(
            OrganizationRoleAssignment.objects.filter(
                organization=recipient,
                role=OrganizationRole.RECIPIENT,
                is_active=True,
            ).exists()
        )
        self.assertTrue(
            RecipientBinding.objects.filter(
                shipper_org=shipper,
                recipient_org=recipient,
                destination=destination,
                is_active=True,
            ).exists()
        )
        self.assertTrue(ContactTag.objects.filter(name="donateur").exists())


class RebuildContactsFromBeXlsxCommandTests(BeWorkbookMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.workbook_path = self._build_be_workbook(
            [
                {
                    "BE_DONATEUR": "Donor A",
                    "ASSOCIATION_NOM": "AVIATION SANS FRONTIERES",
                    "ASSOCIATION_PAYS": "France",
                    "DESTINATAIRE_STRUCTURE": "Recipient A",
                    "DESTINATAIRE_STATUT": "actif",
                    "CORRESPONDANT_PRENOM": "Leontine",
                    "CORRESPONDANT_NOM": "Rahazania",
                    "CORRESPONDANT_PAYS": "Madagascar",
                    "BE_DESTINATION": "ANTANANARIVO",
                    "BE_CODE_IATA": "TNR",
                }
            ]
        )
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        self.report_path = Path(temp_dir.name) / "review.md"

    def test_rebuild_contacts_from_be_xlsx_dry_run_reports_actions_without_database_writes(self):
        stdout = StringIO()

        call_command(
            "rebuild_contacts_from_be_xlsx",
            "--source",
            str(self.workbook_path),
            "--dry-run",
            "--report-path",
            str(self.report_path),
            stdout=stdout,
        )

        output = stdout.getvalue()
        self.assertIn("Rebuild contacts from BE workbook [DRY RUN]", output)
        self.assertIn("Shippers: 1", output)
        self.assertIn("Recipient bindings: 1", output)
        self.assertFalse(Contact.objects.exists())
        self.assertTrue(self.report_path.exists())

    def test_rebuild_contacts_from_be_xlsx_apply_writes_review_report_and_runtime_data(self):
        stdout = StringIO()

        call_command(
            "rebuild_contacts_from_be_xlsx",
            "--source",
            str(self.workbook_path),
            "--apply",
            "--report-path",
            str(self.report_path),
            stdout=stdout,
        )

        output = stdout.getvalue()
        self.assertIn("Rebuild contacts from BE workbook [APPLY]", output)
        self.assertTrue(Contact.objects.exists())
        self.assertTrue(self.report_path.exists())
        self.assertTrue(Destination.objects.filter(iata_code="TNR").exists())
