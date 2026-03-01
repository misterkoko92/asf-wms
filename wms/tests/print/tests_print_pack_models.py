from django.contrib.auth import get_user_model
from django.test import TestCase

from wms.models import (
    GeneratedPrintArtifact,
    GeneratedPrintArtifactItem,
    PrintCellMapping,
    PrintPack,
    PrintPackDocument,
)


class PrintPackModelTests(TestCase):
    def test_pack_models_store_mapping_and_artifact_status(self):
        user = get_user_model().objects.create_user(
            username="printpack-admin",
            password="x",
        )
        pack = PrintPack.objects.create(
            code="B",
            name="Pack B",
            active=True,
            default_page_format="A5",
            fallback_page_format="A4",
        )
        pack_document = PrintPackDocument.objects.create(
            pack=pack,
            doc_type="packing_list_shipment",
            variant="shipment",
            sequence=1,
            enabled=True,
        )
        mapping = PrintCellMapping.objects.create(
            pack_document=pack_document,
            worksheet_name="Main",
            cell_ref="D5",
            source_key="shipment.recipient.full_name",
            transform="upper",
            required=True,
        )
        artifact = GeneratedPrintArtifact.objects.create(
            pack_code=pack.code,
            status="sync_pending",
            created_by=user,
        )
        item = GeneratedPrintArtifactItem.objects.create(
            artifact=artifact,
            doc_type=pack_document.doc_type,
            variant=pack_document.variant,
            sequence=pack_document.sequence,
        )

        self.assertEqual(pack_document.pack.code, "B")
        self.assertEqual(mapping.cell_ref, "D5")
        self.assertEqual(artifact.status, "sync_pending")
        self.assertEqual(item.doc_type, "packing_list_shipment")
