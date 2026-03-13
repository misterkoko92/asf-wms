import base64
import tempfile
from pathlib import Path
from unittest import TestCase, mock


def _import_pdf_render_module(test_case):
    try:
        from tools.planning_comm_helper import pdf_render
    except ImportError as exc:  # pragma: no cover - red phase for TDD
        test_case.fail(f"pdf_render module missing: {exc}")
    return pdf_render


class PlanningCommunicationHelperPdfRenderTests(TestCase):
    def test_render_pdf_job_requires_documents(self):
        pdf_render = _import_pdf_render_module(self)

        with self.assertRaises(pdf_render.PdfRenderJobError) as error:
            pdf_render.render_pdf_job(
                {
                    "documents": [],
                    "output_filename": "planning.pdf",
                }
            )

        self.assertIn("At least one document is required", str(error.exception))

    def test_render_pdf_job_requires_document_filename_and_content(self):
        pdf_render = _import_pdf_render_module(self)

        with self.assertRaises(pdf_render.PdfRenderJobError) as error:
            pdf_render.render_pdf_job(
                {
                    "documents": [{"filename": "", "content_base64": ""}],
                    "output_filename": "planning.pdf",
                }
            )

        self.assertIn("Document filename and content are required", str(error.exception))

    @mock.patch("tools.planning_comm_helper.pdf_render._open_path")
    @mock.patch("tools.planning_comm_helper.pdf_render.convert_workbook_to_pdf")
    def test_render_pdf_job_converts_single_workbook(
        self,
        convert_workbook_to_pdf_mock,
        open_path_mock,
    ):
        pdf_render = _import_pdf_render_module(self)
        with tempfile.TemporaryDirectory() as temp_dir:
            convert_workbook_to_pdf_mock.return_value = (
                Path(temp_dir) / "planning.pdf"
            )
            (Path(temp_dir) / "planning.pdf").write_bytes(b"%PDF-1.4 test")

            result = pdf_render.render_pdf_job(
                {
                    "documents": [
                        {
                            "filename": "planning.xlsx",
                            "content_base64": base64.b64encode(b"xlsx-data").decode("ascii"),
                        }
                    ],
                    "output_filename": "planning.pdf",
                    "open_after_render": True,
                },
                temp_dir=temp_dir,
            )

        convert_workbook_to_pdf_mock.assert_called_once()
        open_path_mock.assert_called_once()
        self.assertEqual(result["output_filename"], "planning.pdf")
        self.assertTrue(result["opened"])

    @mock.patch("tools.planning_comm_helper.pdf_render._open_path")
    @mock.patch("tools.planning_comm_helper.pdf_render.merge_pdf_documents")
    @mock.patch("tools.planning_comm_helper.pdf_render.convert_workbook_to_pdf")
    def test_render_pdf_job_merges_multiple_pdfs(
        self,
        convert_workbook_to_pdf_mock,
        merge_pdf_documents_mock,
        open_path_mock,
    ):
        pdf_render = _import_pdf_render_module(self)
        with tempfile.TemporaryDirectory() as temp_dir:
            first_pdf = Path(temp_dir) / "doc-1.pdf"
            second_pdf = Path(temp_dir) / "doc-2.pdf"
            first_pdf.write_bytes(b"%PDF-1.4 one")
            second_pdf.write_bytes(b"%PDF-1.4 two")
            convert_workbook_to_pdf_mock.side_effect = [first_pdf, second_pdf]
            merge_pdf_documents_mock.return_value = b"%PDF-1.4 merged"

            result = pdf_render.render_pdf_job(
                {
                    "documents": [
                        {
                            "filename": "planning-1.xlsx",
                            "content_base64": base64.b64encode(b"xlsx-one").decode("ascii"),
                        },
                        {
                            "filename": "planning-2.xlsx",
                            "content_base64": base64.b64encode(b"xlsx-two").decode("ascii"),
                        },
                    ],
                    "output_filename": "planning.pdf",
                    "merge": True,
                },
                temp_dir=temp_dir,
            )

        self.assertEqual(convert_workbook_to_pdf_mock.call_count, 2)
        merge_pdf_documents_mock.assert_called_once()
        open_path_mock.assert_not_called()
        self.assertEqual(result["output_filename"], "planning.pdf")
        self.assertFalse(result["opened"])
