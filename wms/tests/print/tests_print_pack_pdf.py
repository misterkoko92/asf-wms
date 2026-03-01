from unittest import mock

from django.test import SimpleTestCase

from wms.print_pack_pdf import PrintPackPdfError, merge_pdf_documents


class PrintPackPdfTests(SimpleTestCase):
    def test_merge_pdf_documents_rejects_empty_input(self):
        with self.assertRaises(PrintPackPdfError):
            merge_pdf_documents([])

    def test_merge_pdf_documents_merges_all_pages(self):
        fake_page_1 = object()
        fake_page_2 = object()
        fake_reader_1 = mock.Mock(pages=[fake_page_1])
        fake_reader_2 = mock.Mock(pages=[fake_page_2])
        fake_writer = mock.Mock()

        def _write(buffer):
            buffer.write(b"%PDF-merged")

        fake_writer.write.side_effect = _write

        with mock.patch(
            "wms.print_pack_pdf.PdfReader",
            side_effect=[fake_reader_1, fake_reader_2],
        ) as reader_mock, mock.patch(
            "wms.print_pack_pdf.PdfWriter",
            return_value=fake_writer,
        ) as writer_mock:
            merged = merge_pdf_documents([b"%PDF-a", b"%PDF-b"])

        self.assertTrue(merged.startswith(b"%PDF"))
        self.assertEqual(reader_mock.call_count, 2)
        writer_mock.assert_called_once()
        self.assertEqual(fake_writer.add_page.call_count, 2)
