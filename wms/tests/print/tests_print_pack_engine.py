from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase

from wms.models import (
    GeneratedPrintArtifactStatus,
    PrintPack,
    PrintPackDocument,
)
from wms.print_pack_engine import generate_pack


class PrintPackEngineTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="print-engine-user",
            password="pass1234",
        )

    def test_generate_pack_creates_single_document_artifact_without_merge(self):
        pack = PrintPack.objects.create(code="A", name="Pack A")
        PrintPackDocument.objects.create(
            pack=pack,
            doc_type="picking",
            variant="single_carton",
            sequence=1,
            enabled=True,
        )

        with mock.patch(
            "wms.print_pack_engine._render_document_xlsx_bytes",
            return_value=b"xlsx-data",
        ) as render_mock, mock.patch(
            "wms.print_pack_engine.convert_excel_to_pdf_via_graph",
            return_value=b"%PDF-single",
        ) as convert_mock, mock.patch(
            "wms.print_pack_engine.merge_pdf_documents"
        ) as merge_mock:
            artifact = generate_pack(pack_code="A", user=self.user)

        self.assertEqual(artifact.pack_code, "A")
        self.assertEqual(artifact.status, GeneratedPrintArtifactStatus.SYNC_PENDING)
        self.assertEqual(artifact.items.count(), 1)
        render_mock.assert_called_once()
        convert_mock.assert_called_once()
        merge_mock.assert_not_called()

    def test_generate_pack_merges_when_multiple_documents_are_present(self):
        pack = PrintPack.objects.create(code="B", name="Pack B")
        PrintPackDocument.objects.create(
            pack=pack,
            doc_type="packing_list_shipment",
            variant="shipment",
            sequence=1,
            enabled=True,
        )
        PrintPackDocument.objects.create(
            pack=pack,
            doc_type="donation_certificate",
            variant="shipment",
            sequence=2,
            enabled=True,
        )

        with mock.patch(
            "wms.print_pack_engine._render_document_xlsx_bytes",
            side_effect=[b"xlsx-1", b"xlsx-2"],
        ), mock.patch(
            "wms.print_pack_engine.convert_excel_to_pdf_via_graph",
            side_effect=[b"%PDF-1", b"%PDF-2"],
        ), mock.patch(
            "wms.print_pack_engine.merge_pdf_documents",
            return_value=b"%PDF-merged",
        ) as merge_mock:
            artifact = generate_pack(pack_code="B", user=self.user)

        self.assertEqual(artifact.items.count(), 2)
        merge_mock.assert_called_once_with([b"%PDF-1", b"%PDF-2"])
        self.assertTrue(artifact.pdf_file.name.endswith(".pdf"))
