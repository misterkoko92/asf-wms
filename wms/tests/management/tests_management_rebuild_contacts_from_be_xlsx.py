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

    def _build_be_multisheet_workbook(self, sheets: dict[str, list[dict]]) -> Path:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        path = Path(temp_dir.name) / "be_source_multisheet.xlsx"

        workbook = Workbook()
        for index, (sheet_name, rows) in enumerate(sheets.items()):
            sheet = workbook.active if index == 0 else workbook.create_sheet()
            sheet.title = sheet_name
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

    def test_build_be_contact_dataset_prefers_latest_sheet_values(self):
        workbook_path = self._build_be_multisheet_workbook(
            {
                "2024": [
                    {
                        "ASSOCIATION_NOM": "AVIATION SANS FRONTIERES",
                        "ASSOCIATION_PAYS": "France",
                        "DESTINATAIRE_STRUCTURE": "Recipient BGF",
                        "DESTINATAIRE_STATUT": "historique",
                        "CORRESPONDANT_PRENOM": "Garba",
                        "CORRESPONDANT_NOM": "TAHA ABOUBAKAR",
                        "CORRESPONDANT_PAYS": "Centrafrique",
                        "BE_DESTINATION": "BANGUI",
                        "BE_CODE_IATA": "BGF",
                    }
                ],
                "2025": [
                    {
                        "ASSOCIATION_NOM": "AVIATION SANS FRONTIERES",
                        "ASSOCIATION_PAYS": "France",
                        "DESTINATAIRE_STRUCTURE": "Recipient BGF",
                        "DESTINATAIRE_STATUT": "actif",
                        "CORRESPONDANT_PRENOM": "Christian",
                        "CORRESPONDANT_NOM": "LIMBIO",
                        "CORRESPONDANT_PAYS": "Centrafrique",
                        "BE_DESTINATION": "BANGUI",
                        "BE_CODE_IATA": "BGF",
                    }
                ],
                "2026": [
                    {
                        "ASSOCIATION_NOM": "AVIATION SANS FRONTIERES",
                        "ASSOCIATION_PAYS": "France",
                        "DESTINATAIRE_STRUCTURE": "Recipient BGF",
                        "DESTINATAIRE_STATUT": "prioritaire",
                        "CORRESPONDANT_PRENOM": "Christian",
                        "CORRESPONDANT_NOM": "LIMBIO",
                        "CORRESPONDANT_PAYS": "Centrafrique",
                        "BE_DESTINATION": "BANGUI",
                        "BE_CODE_IATA": "BGF",
                    }
                ],
            }
        )

        dataset = build_be_contact_dataset(workbook_path)

        self.assertEqual(dataset.source_sheets, ["2024", "2025", "2026"])
        self.assertEqual(
            dataset.recipients,
            [{"key": "recipient bgf", "name": "Recipient BGF", "status": "prioritaire"}],
        )
        self.assertEqual(
            dataset.correspondents,
            [
                {
                    "key": "christian limbio",
                    "name": "Christian LIMBIO",
                    "country": "Centrafrique",
                }
            ],
        )
        self.assertEqual(
            dataset.destinations,
            [
                {
                    "key": "BGF",
                    "city": "BANGUI",
                    "country": "Centrafrique",
                    "iata_code": "BGF",
                    "correspondent_key": "christian limbio",
                }
            ],
        )
        self.assertEqual(dataset.review_items, [])

    def test_build_be_contact_dataset_applies_explicit_correspondent_overrides(self):
        workbook_path = self._build_be_multisheet_workbook(
            {
                "2024": [
                    {
                        "ASSOCIATION_NOM": "AVIATION SANS FRONTIERES",
                        "ASSOCIATION_PAYS": "France",
                        "DESTINATAIRE_STRUCTURE": "Recipient BEY",
                        "DESTINATAIRE_STATUT": "actif",
                        "CORRESPONDANT_PRENOM": "Ancien",
                        "CORRESPONDANT_NOM": "Correspondant",
                        "CORRESPONDANT_PAYS": "Liban",
                        "BE_DESTINATION": "BEYROUTH",
                        "BE_CODE_IATA": "BEY",
                    }
                ],
                "2025": [
                    {
                        "ASSOCIATION_NOM": "AVIATION SANS FRONTIERES",
                        "ASSOCIATION_PAYS": "France",
                        "DESTINATAIRE_STRUCTURE": "Recipient BGF",
                        "DESTINATAIRE_STATUT": "actif",
                        "CORRESPONDANT_PRENOM": "Garba",
                        "CORRESPONDANT_NOM": "TAHA ABOUBAKAR",
                        "CORRESPONDANT_PAYS": "Centrafrique",
                        "BE_DESTINATION": "BANGUI",
                        "BE_CODE_IATA": "BGF",
                    }
                ],
                "2026": [
                    {
                        "ASSOCIATION_NOM": "AVIATION SANS FRONTIERES",
                        "ASSOCIATION_PAYS": "France",
                        "DESTINATAIRE_STRUCTURE": "Recipient NDJ",
                        "DESTINATAIRE_STATUT": "actif",
                        "CORRESPONDANT_PRENOM": "Rocher",
                        "CORRESPONDANT_NOM": "DJEGUERBE MBAIOUNDADE",
                        "CORRESPONDANT_PAYS": "Tchad",
                        "BE_DESTINATION": "N'DJAMENA",
                        "BE_CODE_IATA": "NDJ",
                    }
                ],
            }
        )

        dataset = build_be_contact_dataset(workbook_path)
        destinations_by_iata = {
            destination["iata_code"]: destination for destination in dataset.destinations
        }
        correspondents_by_key = {
            correspondent["key"]: correspondent for correspondent in dataset.correspondents
        }

        self.assertEqual(destinations_by_iata["BEY"]["correspondent_key"], "tony mdawar")
        self.assertEqual(
            correspondents_by_key["tony mdawar"]["name"],
            "Tony MDAWAR",
        )
        self.assertEqual(
            destinations_by_iata["BGF"]["correspondent_key"],
            "christian limbio",
        )
        self.assertEqual(
            correspondents_by_key["christian limbio"]["name"],
            "Christian LIMBIO",
        )
        self.assertEqual(
            destinations_by_iata["NDJ"]["correspondent_key"],
            "geovanie kamtar ndangmbaye",
        )
        self.assertEqual(
            correspondents_by_key["geovanie kamtar ndangmbaye"]["name"],
            "Geovanie Kamtar NDANGMBAYE",
        )
        self.assertEqual(dataset.review_items, [])


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
        self.assertFalse(shipper.destinations.exists())
        self.assertIsNone(shipper.destination_id)
        self.assertFalse(recipient.destinations.exists())
        self.assertIsNone(recipient.destination_id)
        self.assertFalse(recipient.linked_shippers.exists())
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

    def test_rebuild_contacts_from_be_xlsx_reports_selected_source_sheets(self):
        workbook_path = self._build_be_multisheet_workbook(
            {
                "2024": [
                    {
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
                ],
                "2025": [],
                "2026": [],
            }
        )
        stdout = StringIO()

        call_command(
            "rebuild_contacts_from_be_xlsx",
            "--source",
            str(workbook_path),
            "--dry-run",
            "--report-path",
            str(self.report_path),
            stdout=stdout,
        )

        output = stdout.getvalue()
        self.assertIn("Source sheets: 2024, 2025, 2026", output)


class RebuildContactsOrgRolesCanonicalCommandTests(BeWorkbookMixin, TestCase):
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
        self.report_path = Path(temp_dir.name) / "canonical-review.md"

        self.existing_shipper = Contact.objects.create(
            name="Legacy Shipper",
            contact_type=ContactType.ORGANIZATION,
        )
        self.existing_recipient = Contact.objects.create(
            name="Legacy Recipient",
            contact_type=ContactType.ORGANIZATION,
        )
        self.existing_correspondent = Contact.objects.create(
            name="Legacy Correspondent",
            contact_type=ContactType.ORGANIZATION,
        )
        self.existing_destination = Destination.objects.create(
            city="Legacy City",
            iata_code="OLD",
            country="France",
            correspondent_contact=self.existing_correspondent,
            is_active=True,
        )
        self.existing_shipper_assignment = OrganizationRoleAssignment.objects.create(
            organization=self.existing_shipper,
            role=OrganizationRole.SHIPPER,
            is_active=True,
        )
        RecipientBinding.objects.create(
            shipper_org=self.existing_shipper,
            recipient_org=self.existing_recipient,
            destination=self.existing_destination,
            is_active=True,
        )

    def test_canonical_command_dry_run_leaves_existing_runtime_data_untouched(self):
        stdout = StringIO()

        call_command(
            "rebuild_contacts_org_roles_canonical",
            "--source",
            str(self.workbook_path),
            "--dry-run",
            "--report-path",
            str(self.report_path),
            stdout=stdout,
        )

        output = stdout.getvalue()
        self.assertIn("Canonical org-roles contact rebuild [DRY RUN]", output)
        self.assertIn("Review report:", output)
        self.assertTrue(Contact.objects.filter(pk=self.existing_shipper.pk).exists())
        self.assertTrue(Destination.objects.filter(pk=self.existing_destination.pk).exists())
        self.assertTrue(
            OrganizationRoleAssignment.objects.filter(
                pk=self.existing_shipper_assignment.pk
            ).exists()
        )
        self.assertFalse(Contact.objects.filter(name="AVIATION SANS FRONTIERES").exists())
        self.assertTrue(self.report_path.exists())

    def test_canonical_command_apply_resets_then_imports_workbook_data(self):
        stdout = StringIO()

        call_command(
            "rebuild_contacts_org_roles_canonical",
            "--source",
            str(self.workbook_path),
            "--apply",
            "--report-path",
            str(self.report_path),
            stdout=stdout,
        )

        output = stdout.getvalue()
        self.assertIn("Canonical org-roles contact rebuild [APPLY]", output)
        self.assertFalse(Contact.objects.filter(pk=self.existing_shipper.pk).exists())
        self.assertFalse(Destination.objects.filter(pk=self.existing_destination.pk).exists())
        self.assertTrue(Contact.objects.filter(name="AVIATION SANS FRONTIERES").exists())
        self.assertTrue(Contact.objects.filter(name="Recipient A").exists())
        self.assertTrue(Destination.objects.filter(iata_code="TNR").exists())
        self.assertTrue(
            RecipientBinding.objects.filter(
                shipper_org__name="AVIATION SANS FRONTIERES",
                recipient_org__name="Recipient A",
                destination__iata_code="TNR",
                is_active=True,
            ).exists()
        )
        self.assertTrue(self.report_path.exists())
