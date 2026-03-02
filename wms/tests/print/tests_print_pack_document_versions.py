from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.db import IntegrityError
from django.test import TestCase

from wms import models


class PrintPackDocumentVersionModelTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="pack-version-user",
            password="pass1234",
        )
        self.pack = models.PrintPack.objects.create(code="PV", name="Pack Version")
        self.pack_document = models.PrintPackDocument.objects.create(
            pack=self.pack,
            doc_type="picking",
            variant="single_carton",
            sequence=1,
            enabled=True,
        )

    def test_can_store_xlsx_snapshot_and_mapping_snapshot(self):
        version = models.PrintPackDocumentVersion.objects.create(
            pack_document=self.pack_document,
            version=1,
            mappings_snapshot=[
                {
                    "worksheet_name": "Feuil1",
                    "cell_ref": "A11",
                    "source_key": "carton.code",
                    "transform": "",
                    "required": True,
                    "sequence": 1,
                }
            ],
            change_type="save",
            created_by=self.user,
        )
        version.xlsx_template_file.save(
            "PV__picking__single_carton.xlsx",
            ContentFile(b"fake-xlsx-bytes"),
            save=True,
        )

        version.refresh_from_db()
        self.assertEqual(version.pack_document_id, self.pack_document.id)
        self.assertEqual(version.version, 1)
        self.assertEqual(version.change_type, "save")
        self.assertEqual(version.created_by_id, self.user.id)
        self.assertTrue(version.xlsx_template_file.name.endswith(".xlsx"))
        self.assertEqual(version.mappings_snapshot[0]["cell_ref"], "A11")

    def test_unique_together_pack_document_and_version(self):
        models.PrintPackDocumentVersion.objects.create(
            pack_document=self.pack_document,
            version=1,
            mappings_snapshot=[],
            change_type="save",
            created_by=self.user,
        )
        with self.assertRaises(IntegrityError):
            models.PrintPackDocumentVersion.objects.create(
                pack_document=self.pack_document,
                version=1,
                mappings_snapshot=[],
                change_type="save",
                created_by=self.user,
            )
