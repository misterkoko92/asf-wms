from unittest import mock

from django.test import SimpleTestCase

from wms.print_pack_pdf import (
    PrintPackPdfError,
    impose_two_up_pdf_on_a4,
    merge_pdf_documents,
)


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

        with (
            mock.patch(
                "wms.print_pack_pdf.PdfReader",
                side_effect=[fake_reader_1, fake_reader_2],
            ) as reader_mock,
            mock.patch(
                "wms.print_pack_pdf.PdfWriter",
                return_value=fake_writer,
            ) as writer_mock,
        ):
            merged = merge_pdf_documents([b"%PDF-a", b"%PDF-b"])

        self.assertTrue(merged.startswith(b"%PDF"))
        self.assertEqual(reader_mock.call_count, 2)
        writer_mock.assert_called_once()
        self.assertEqual(fake_writer.add_page.call_count, 2)

    def test_impose_two_up_pdf_on_a4_rejects_empty_input(self):
        with self.assertRaises(PrintPackPdfError):
            impose_two_up_pdf_on_a4([])

    def test_impose_two_up_pdf_on_a4_places_two_pages_on_one_sheet(self):
        fake_page_1 = mock.Mock()
        fake_page_1.mediabox.width = 420
        fake_page_1.mediabox.height = 595
        fake_page_2 = mock.Mock()
        fake_page_2.mediabox.width = 420
        fake_page_2.mediabox.height = 595
        fake_reader_1 = mock.Mock(pages=[fake_page_1])
        fake_reader_2 = mock.Mock(pages=[fake_page_2])
        fake_sheet = mock.Mock()
        fake_writer = mock.Mock()
        fake_writer.add_blank_page.return_value = fake_sheet

        first_transform = mock.Mock()
        first_transform.scale.return_value = first_transform
        first_transform.translate.return_value = "transform-top"
        second_transform = mock.Mock()
        second_transform.scale.return_value = second_transform
        second_transform.translate.return_value = "transform-bottom"

        def _write(buffer):
            buffer.write(b"%PDF-two-up")

        fake_writer.write.side_effect = _write

        with (
            mock.patch(
                "wms.print_pack_pdf.PdfReader",
                side_effect=[fake_reader_1, fake_reader_2],
            ),
            mock.patch(
                "wms.print_pack_pdf.PdfWriter",
                return_value=fake_writer,
            ),
            mock.patch(
                "wms.print_pack_pdf.Transformation",
                side_effect=[first_transform, second_transform],
            ),
        ):
            merged = impose_two_up_pdf_on_a4([b"%PDF-a", b"%PDF-b"])

        self.assertTrue(merged.startswith(b"%PDF"))
        fake_writer.add_blank_page.assert_called_once()
        self.assertEqual(fake_sheet.merge_transformed_page.call_count, 2)
        first_transform.scale.assert_called_once()
        second_transform.scale.assert_called_once()
