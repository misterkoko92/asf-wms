from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.test import TestCase

from wms.models import PrintCellMapping, PrintPack, PrintPackDocument
from wms.print_pack_template_versions import (
    restore_print_pack_document_version,
    save_print_pack_document_snapshot,
)


def _read_file_bytes(file_field):
    with file_field.open("rb") as stream:
        return stream.read()


class PrintPackTemplateVersionServicesTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="print-pack-version-service-user",
            password="pass1234",
        )
        self.pack = PrintPack.objects.create(code="VS", name="Version Service")
        self.pack_document = PrintPackDocument.objects.create(
            pack=self.pack,
            doc_type="picking",
            variant="single_carton",
            sequence=1,
            enabled=True,
        )
        self.pack_document.xlsx_template_file.save(
            "VS__picking__single_carton.xlsx",
            ContentFile(b"xlsx-v1"),
            save=True,
        )
        PrintCellMapping.objects.create(
            pack_document=self.pack_document,
            worksheet_name="Feuil1",
            cell_ref="A11",
            source_key="carton.code",
            transform="",
            required=True,
            sequence=1,
        )

    def test_save_print_pack_document_snapshot_creates_incremental_versions(self):
        first = save_print_pack_document_snapshot(
            pack_document=self.pack_document,
            created_by=self.user,
            change_type="save",
            change_note="first",
        )
        self.assertEqual(first.version, 1)
        self.assertEqual(first.change_type, "save")
        self.assertEqual(first.change_note, "first")
        self.assertEqual(first.mappings_snapshot[0]["cell_ref"], "A11")
        self.assertEqual(_read_file_bytes(first.xlsx_template_file), b"xlsx-v1")

        mapping = self.pack_document.cell_mappings.get(cell_ref="A11")
        mapping.source_key = "carton.position"
        mapping.save(update_fields=["source_key"])
        second = save_print_pack_document_snapshot(
            pack_document=self.pack_document,
            created_by=self.user,
            change_type="save",
            change_note="second",
        )
        self.assertEqual(second.version, 2)
        self.assertEqual(second.mappings_snapshot[0]["source_key"], "carton.position")

    def test_restore_print_pack_document_version_reapplies_file_and_mappings(self):
        version = save_print_pack_document_snapshot(
            pack_document=self.pack_document,
            created_by=self.user,
            change_type="save",
        )
        self.pack_document.xlsx_template_file.save(
            "VS__picking__single_carton--edited.xlsx",
            ContentFile(b"xlsx-v2"),
            save=True,
        )
        mapping = self.pack_document.cell_mappings.get(cell_ref="A11")
        mapping.source_key = "carton.position"
        mapping.save(update_fields=["source_key"])

        restore_version = restore_print_pack_document_version(
            version=version,
            created_by=self.user,
            change_note="rollback",
        )

        self.pack_document.refresh_from_db()
        restored_mapping = self.pack_document.cell_mappings.get(cell_ref="A11")
        self.assertEqual(restored_mapping.source_key, "carton.code")
        self.assertEqual(_read_file_bytes(self.pack_document.xlsx_template_file), b"xlsx-v1")
        self.assertEqual(restore_version.version, 2)
        self.assertEqual(restore_version.change_type, "restore")
        self.assertEqual(restore_version.change_note, "rollback")
