import tempfile
from io import StringIO
from pathlib import Path
from unittest import mock

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from contacts.models import Contact, ContactAddress, ContactTag, ContactType
from wms.management.commands import import_wms_data
from wms.models import Destination


class ImportWmsDataHelpersTests(TestCase):
    def test_text_and_email_helpers(self):
        self.assertEqual(import_wms_data.normalize_header("  Nom  "), "nom")
        self.assertEqual(import_wms_data.clean_text(None), "")
        self.assertEqual(import_wms_data.clean_text(12.0), "12")
        self.assertEqual(import_wms_data.clean_text("  abc "), "abc")
        self.assertEqual(import_wms_data.normalize_text("  a   b  "), "a b")
        self.assertEqual(import_wms_data.normalize_address(""), "")
        self.assertEqual(
            import_wms_data.normalize_address("  1 rue \n\n Paris \r\n France "),
            "1 rue, Paris, France",
        )
        self.assertEqual(import_wms_data.normalize_key("  PaRiS  "), "paris")

        self.assertIsNone(import_wms_data.parse_bool(""))
        self.assertTrue(import_wms_data.parse_bool("oui"))
        self.assertFalse(import_wms_data.parse_bool("non"))

        self.assertEqual(import_wms_data.extract_email("contact@example.org"), "contact@example.org")
        self.assertEqual(import_wms_data.extract_email("bad mail"), "")
        self.assertEqual(import_wms_data.extract_email(""), "")

        self.assertEqual(import_wms_data.append_note("", " new "), "new")
        self.assertEqual(import_wms_data.append_note("existing", ""), "existing")
        self.assertEqual(import_wms_data.append_note("one", "two"), "one\ntwo")
        self.assertEqual(import_wms_data.append_note("one\ntwo", "two"), "one\ntwo")

    def test_ensure_tag_and_get_cell(self):
        tag = import_wms_data.ensure_tag("  ExPediteur ")
        self.assertEqual(tag.name, "expediteur")

        row = ["", "fallback@example.org", "main@example.org"]
        header_map = {"email": [0, 1, 2]}
        self.assertEqual(
            import_wms_data.get_cell(row, header_map, "email"),
            "fallback@example.org",
        )
        self.assertIsNone(import_wms_data.get_cell(row, header_map, "missing"))

    def test_iter_excel_rows_branches(self):
        with mock.patch.object(import_wms_data, "load_workbook", None):
            with self.assertRaisesMessage(CommandError, "openpyxl is required"):
                list(import_wms_data.iter_excel_rows(Path("input.xlsx")))

        empty_workbook = mock.Mock()
        empty_workbook.active.iter_rows.return_value = iter(())
        with mock.patch.object(import_wms_data, "load_workbook", return_value=empty_workbook):
            with self.assertRaisesMessage(CommandError, "Excel file is empty"):
                list(import_wms_data.iter_excel_rows(Path("input.xlsx")))

        workbook = mock.Mock()
        workbook.active.iter_rows.return_value = iter(
            [
                ("Email", "", "Nom"),
                ("", "", ""),
                ("main@example.org", "ignored", "Association A"),
            ]
        )
        with mock.patch.object(import_wms_data, "load_workbook", return_value=workbook):
            rows = list(import_wms_data.iter_excel_rows(Path("ok.xlsx")))

        self.assertEqual(len(rows), 1)
        row, header_map = rows[0]
        self.assertEqual(row[0], "main@example.org")
        self.assertEqual(header_map["email"], [0])
        self.assertEqual(header_map["nom"], [2])
        workbook.close.assert_called_once()

    def test_upsert_contact_create_update_and_no_name(self):
        contact, created, updated = import_wms_data.upsert_contact(
            name=" Association A ",
            tag_name=import_wms_data.TAG_SHIPPER,
            contact_type=ContactType.ORGANIZATION,
            email="a@example.org",
            phone="123",
            notes="note 1",
            active=True,
        )
        self.assertTrue(created)
        self.assertTrue(updated)
        self.assertEqual(contact.name, "Association A")
        self.assertEqual(contact.email, "a@example.org")
        self.assertEqual(contact.phone, "123")
        self.assertIn("note 1", contact.notes)
        self.assertTrue(contact.tags.filter(name=import_wms_data.TAG_SHIPPER).exists())

        contact.email = ""
        contact.phone = ""
        contact.notes = ""
        contact.is_active = False
        contact.save()

        same, created, updated = import_wms_data.upsert_contact(
            name="association a",
            tag_name=import_wms_data.TAG_SHIPPER,
            contact_type=ContactType.ORGANIZATION,
            email="new@example.org",
            phone="456",
            notes="note 2",
            active=True,
        )
        self.assertEqual(same.id, contact.id)
        self.assertFalse(created)
        self.assertTrue(updated)
        same.refresh_from_db()
        self.assertEqual(same.email, "new@example.org")
        self.assertEqual(same.phone, "456")
        self.assertTrue(same.is_active)

        empty, created, updated = import_wms_data.upsert_contact(
            name="",
            tag_name=import_wms_data.TAG_SHIPPER,
            contact_type=ContactType.ORGANIZATION,
        )
        self.assertIsNone(empty)
        self.assertFalse(created)
        self.assertFalse(updated)

    def test_upsert_address_create_duplicate_and_defaulting(self):
        contact = Contact.objects.create(
            name="Association B",
            contact_type=ContactType.ORGANIZATION,
        )
        self.assertFalse(
            import_wms_data.upsert_address(
                contact=contact,
                address_line1="",
                city="Paris",
                postal_code="75001",
                country="France",
            )
        )

        created = import_wms_data.upsert_address(
            contact=contact,
            address_line1="10 rue test",
            city="Paris",
            postal_code="75001",
            country="",
        )
        self.assertTrue(created)
        first = contact.addresses.get()
        self.assertTrue(first.is_default)
        self.assertEqual(first.country, "France")

        duplicate = import_wms_data.upsert_address(
            contact=contact,
            address_line1="10 rue test",
            city="Paris",
            postal_code="75001",
            country="France",
        )
        self.assertFalse(duplicate)

        second_created = import_wms_data.upsert_address(
            contact=contact,
            address_line1="20 rue test",
            city="Lyon",
            postal_code="69001",
            country="France",
        )
        self.assertTrue(second_created)
        self.assertEqual(contact.addresses.filter(is_default=True).count(), 1)

    def test_merge_association_tags_moves_contacts(self):
        legacy_a = ContactTag.objects.create(name="association")
        legacy_b = ContactTag.objects.create(name="nom association")
        contact = Contact.objects.create(
            name="Association C",
            contact_type=ContactType.ORGANIZATION,
        )
        contact.tags.add(legacy_a, legacy_b)

        import_wms_data.merge_association_tags()

        self.assertTrue(
            contact.tags.filter(name=import_wms_data.TAG_SHIPPER).exists()
        )
        self.assertFalse(ContactTag.objects.filter(name="association").exists())
        self.assertFalse(ContactTag.objects.filter(name="nom association").exists())


class ImportWmsDataCommandTests(TestCase):
    def _stats(self):
        return {
            "contacts_created": 0,
            "contacts_updated": 0,
            "addresses_created": 0,
            "destinations_created": 0,
            "destinations_updated": 0,
            "rows_skipped": 0,
            "warnings": 0,
        }

    def _new_command(self):
        command = import_wms_data.Command()
        command.stdout = StringIO()
        command.stderr = StringIO()
        return command

    def _touch_file(self, suffix=".xlsx"):
        tmp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(tmp_dir.cleanup)
        path = Path(tmp_dir.name) / f"input{suffix}"
        path.write_text("x", encoding="utf-8")
        return path

    def test_handle_raises_on_missing_folder(self):
        with self.assertRaisesMessage(CommandError, "Folder not found"):
            call_command("import_wms_data", "/tmp/folder-missing")

    def test_handle_dry_run_rolls_back(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir)
            out = StringIO()

            def fake_import_donors(self, import_path, stats):
                Contact.objects.create(
                    name="Temp Dry",
                    contact_type=ContactType.ORGANIZATION,
                )
                stats["contacts_created"] += 1

            with mock.patch.object(
                import_wms_data.Command,
                "_import_donors",
                new=fake_import_donors,
            ), mock.patch.object(
                import_wms_data.Command,
                "_import_shippers",
                return_value=None,
            ), mock.patch.object(
                import_wms_data.Command,
                "_import_recipients",
                return_value=None,
            ), mock.patch.object(
                import_wms_data.Command,
                "_import_correspondents",
                return_value=None,
            ), mock.patch.object(
                import_wms_data.Command,
                "_import_destinations",
                return_value=None,
            ):
                call_command("import_wms_data", str(path), "--dry-run", stdout=out)

        self.assertFalse(Contact.objects.filter(name="Temp Dry").exists())
        self.assertIn("Dry run complete; no changes were saved.", out.getvalue())
        self.assertIn("1 contacts crees", out.getvalue())

    def test_import_methods_missing_files_increment_warnings(self):
        command = self._new_command()
        stats = self._stats()
        missing = Path("/tmp/absent.xlsx")

        command._import_donors(missing, stats)
        command._import_shippers(missing, stats)
        command._import_recipients(missing, stats)
        command._import_correspondents(missing, stats)
        command._import_destinations(missing, stats)

        self.assertEqual(stats["warnings"], 5)
        self.assertEqual(command.stderr.getvalue().count("Fichier manquant"), 5)

    def test_import_donors_processes_rows(self):
        command = self._new_command()
        stats = self._stats()
        path = self._touch_file()
        header_map = {"be_donateur": [0]}
        rows = [([""], header_map), (["Donor A"], header_map), (["Donor B"], header_map)]

        with mock.patch(
            "wms.management.commands.import_wms_data.iter_excel_rows",
            return_value=iter(rows),
        ), mock.patch(
            "wms.management.commands.import_wms_data.upsert_contact",
            side_effect=[
                (mock.sentinel.contact_a, True, False),
                (mock.sentinel.contact_b, False, True),
            ],
        ) as upsert_contact_mock:
            command._import_donors(path, stats)

        self.assertEqual(stats["rows_skipped"], 1)
        self.assertEqual(stats["contacts_created"], 1)
        self.assertEqual(stats["contacts_updated"], 1)
        kwargs = upsert_contact_mock.call_args.kwargs
        self.assertEqual(kwargs["name"], "Donor B")
        self.assertEqual(kwargs["tag_name"], import_wms_data.TAG_DONOR)
        self.assertEqual(kwargs["contact_type"], ContactType.ORGANIZATION)

    def test_import_shippers_processes_rows_and_address(self):
        command = self._new_command()
        stats = self._stats()
        path = self._touch_file()
        header_map = {
            "association_nom": [0],
            "association_active": [1],
            "association_president_titre": [2],
            "association_president_prenom": [3],
            "association_president_nom": [4],
            "association_email": [5],
            "association_tel_1": [6],
            "association_tel_2": [7],
            "association_adresse": [8],
            "association_ville": [9],
            "association_code_postal": [10],
            "association_pays": [11],
        }
        rows = [
            (["", "", "", "", "", "", "", "", "", "", "", ""], header_map),
            (
                [
                    "Association A",
                    "oui",
                    "Dr",
                    "Jane",
                    "Doe",
                    "ship@example.org",
                    "111",
                    "222",
                    "10 Rue A",
                    "Paris",
                    "75001",
                    "France",
                ],
                header_map,
            ),
            (
                [
                    "Association B",
                    "oui",
                    "",
                    "",
                    "",
                    "ship2@example.org",
                    "333",
                    "",
                    "11 Rue B",
                    "Lyon",
                    "69001",
                    "France",
                ],
                header_map,
            ),
        ]
        with mock.patch(
            "wms.management.commands.import_wms_data.iter_excel_rows",
            return_value=iter(rows),
        ), mock.patch(
            "wms.management.commands.import_wms_data.upsert_contact",
            side_effect=[
                (mock.sentinel.contact_a, True, False),
                (mock.sentinel.contact_b, False, True),
            ],
        ) as upsert_contact_mock, mock.patch(
            "wms.management.commands.import_wms_data.upsert_address",
            return_value=True,
        ) as upsert_address_mock:
            command._import_shippers(path, stats)

        self.assertEqual(stats["rows_skipped"], 1)
        self.assertEqual(stats["contacts_created"], 1)
        self.assertEqual(stats["contacts_updated"], 1)
        self.assertEqual(stats["addresses_created"], 2)

        kwargs = upsert_contact_mock.call_args_list[0].kwargs
        self.assertEqual(kwargs["name"], "Association A")
        self.assertEqual(kwargs["tag_name"], import_wms_data.TAG_SHIPPER)
        self.assertEqual(kwargs["contact_type"], ContactType.ORGANIZATION)
        self.assertEqual(kwargs["email"], "ship@example.org")
        self.assertEqual(kwargs["phone"], "111")
        self.assertTrue(kwargs["active"])
        self.assertIn("President: Dr Jane Doe", kwargs["notes"])
        self.assertIn("Tel 2: 222", kwargs["notes"])
        self.assertEqual(upsert_address_mock.call_count, 2)

    def test_import_recipients_processes_rows_and_address(self):
        command = self._new_command()
        stats = self._stats()
        path = self._touch_file()
        header_map = {
            "destinataire_structure": [0],
            "destinataire_statut": [1],
            "destinataire_structure_tel_1": [2],
            "destinataire_structure_tel_2": [3],
            "destinataire_structure_adresse": [4],
            "destinataire_structure_ville": [5],
            "destinataire_structure_code_postal": [6],
            "destinataire_structure_pays": [7],
        }
        rows = [
            (["", "", "", "", "", "", "", ""], header_map),
            (
                [
                    "Hopital A",
                    "Actif",
                    "333",
                    "444",
                    "20 Rue B",
                    "Lyon",
                    "69000",
                    "France",
                ],
                header_map,
            ),
            (
                [
                    "Hopital B",
                    "",
                    "777",
                    "",
                    "21 Rue B",
                    "Nice",
                    "06000",
                    "France",
                ],
                header_map,
            ),
        ]
        with mock.patch(
            "wms.management.commands.import_wms_data.iter_excel_rows",
            return_value=iter(rows),
        ), mock.patch(
            "wms.management.commands.import_wms_data.upsert_contact",
            side_effect=[
                (mock.sentinel.contact_a, True, False),
                (mock.sentinel.contact_b, False, True),
            ],
        ) as upsert_contact_mock, mock.patch(
            "wms.management.commands.import_wms_data.upsert_address",
            return_value=True,
        ):
            command._import_recipients(path, stats)

        self.assertEqual(stats["rows_skipped"], 1)
        self.assertEqual(stats["contacts_created"], 1)
        self.assertEqual(stats["contacts_updated"], 1)
        self.assertEqual(stats["addresses_created"], 2)
        kwargs = upsert_contact_mock.call_args_list[0].kwargs
        self.assertEqual(kwargs["name"], "Hopital A")
        self.assertEqual(kwargs["tag_name"], import_wms_data.TAG_RECIPIENT)
        self.assertEqual(kwargs["contact_type"], ContactType.ORGANIZATION)
        self.assertEqual(kwargs["phone"], "333")
        self.assertTrue(kwargs["active"])
        self.assertIn("Statut: Actif", kwargs["notes"])
        self.assertIn("Tel 2: 444", kwargs["notes"])

    def test_import_correspondents_processes_rows_and_address(self):
        command = self._new_command()
        stats = self._stats()
        path = self._touch_file()
        header_map = {
            "correspondant_titre": [0],
            "correspondant_prenom": [1],
            "correspondant_nom": [2],
            "correspondant_tel_1": [3],
            "correspondant_tel_2": [4],
            "correspondant_adresse": [5],
            "correspondant_ville": [6],
            "correspondant_code_postal": [7],
            "correspondant_pays": [8],
        }
        rows = [
            (["", "", "", "", "", "", "", "", ""], header_map),
            (
                [
                    "Mme",
                    "Alice",
                    "Martin",
                    "555",
                    "666",
                    "30 Rue C",
                    "Paris",
                    "75002",
                    "France",
                ],
                header_map,
            ),
            (
                [
                    "",
                    "Bob",
                    "Durand",
                    "777",
                    "",
                    "31 Rue D",
                    "Lille",
                    "59000",
                    "France",
                ],
                header_map,
            ),
        ]
        with mock.patch(
            "wms.management.commands.import_wms_data.iter_excel_rows",
            return_value=iter(rows),
        ), mock.patch(
            "wms.management.commands.import_wms_data.upsert_contact",
            side_effect=[
                (mock.sentinel.contact_a, True, False),
                (mock.sentinel.contact_b, False, True),
            ],
        ) as upsert_contact_mock, mock.patch(
            "wms.management.commands.import_wms_data.upsert_address",
            return_value=True,
        ):
            command._import_correspondents(path, stats)

        self.assertEqual(stats["rows_skipped"], 1)
        self.assertEqual(stats["contacts_created"], 1)
        self.assertEqual(stats["contacts_updated"], 1)
        self.assertEqual(stats["addresses_created"], 2)
        kwargs = upsert_contact_mock.call_args_list[0].kwargs
        self.assertEqual(kwargs["name"], "Alice Martin")
        self.assertEqual(kwargs["tag_name"], import_wms_data.TAG_CORRESPONDENT)
        self.assertEqual(kwargs["contact_type"], ContactType.PERSON)
        self.assertEqual(kwargs["phone"], "555")
        self.assertTrue(kwargs["active"])
        self.assertIn("Titre: Mme", kwargs["notes"])
        self.assertIn("Tel 2: 666", kwargs["notes"])

    def test_build_correspondent_map_warns_on_duplicates(self):
        tag = ContactTag.objects.create(name=import_wms_data.TAG_CORRESPONDENT)

        first = Contact.objects.create(name="A Contact", contact_type=ContactType.PERSON)
        second = Contact.objects.create(name="B Contact", contact_type=ContactType.PERSON)
        third = Contact.objects.create(name="C Contact", contact_type=ContactType.PERSON)
        first.tags.add(tag)
        second.tags.add(tag)
        third.tags.add(tag)

        ContactAddress.objects.create(
            contact=first,
            address_line1="1 Rue",
            city="Paris",
            country="France",
            is_default=True,
        )
        ContactAddress.objects.create(
            contact=second,
            address_line1="2 Rue",
            city="Paris",
            country="France",
            is_default=True,
        )
        ContactAddress.objects.create(
            contact=third,
            address_line1="3 Rue",
            city="",
            country="France",
            is_default=True,
        )

        command = self._new_command()
        stats = self._stats()
        mapping = command._build_correspondent_map(stats)

        self.assertEqual(mapping[("paris", "france")].id, first.id)
        self.assertEqual(stats["warnings"], 1)
        self.assertIn(
            "Correspondants multiples pour Paris, France.",
            command.stderr.getvalue(),
        )

    def test_import_destinations_create_update_skip_and_warnings(self):
        correspondent = Contact.objects.create(
            name="Correspondent A",
            contact_type=ContactType.PERSON,
        )
        other = Contact.objects.create(
            name="Other Correspondent",
            contact_type=ContactType.PERSON,
        )
        existing = Destination.objects.create(
            city="Old City",
            country="Old Country",
            iata_code="CDG",
            correspondent_contact=other,
            is_active=False,
        )

        command = self._new_command()
        stats = self._stats()
        path = self._touch_file()
        header_map = {
            "destination_ville": [0],
            "destination_pays": [1],
            "destination_iata": [2],
        }
        rows = [
            (["", "France", "XXX"], header_map),
            (["Lyon", "France", "LYS"], header_map),
            (["Paris", "France", "cdg"], header_map),
            (["Marseille", "France", "MRS"], header_map),
        ]
        mapping = {
            ("paris", "france"): correspondent,
            ("marseille", "france"): correspondent,
        }
        with mock.patch.object(command, "_build_correspondent_map", return_value=mapping), mock.patch(
            "wms.management.commands.import_wms_data.iter_excel_rows",
            return_value=iter(rows),
        ):
            command._import_destinations(path, stats)

        existing.refresh_from_db()
        self.assertEqual(existing.city, "Paris")
        self.assertEqual(existing.country, "France")
        self.assertEqual(existing.correspondent_contact_id, correspondent.id)
        self.assertTrue(existing.is_active)
        self.assertTrue(Destination.objects.filter(iata_code="MRS").exists())
        self.assertEqual(stats["rows_skipped"], 1)
        self.assertEqual(stats["warnings"], 1)
        self.assertEqual(stats["destinations_updated"], 1)
        self.assertEqual(stats["destinations_created"], 1)
        self.assertIn(
            "Destination sans correspondant: Lyon, France (LYS)",
            command.stderr.getvalue(),
        )
