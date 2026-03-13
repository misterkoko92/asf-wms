import tempfile
from pathlib import Path
from unittest import TestCase, mock

from tools.planning_comm_helper import excel_pdf
from tools.planning_comm_helper.planning_pdf import (
    PlanningPdfConversionError,
    convert_workbook_to_pdf,
)


class PlanningCommunicationHelperPlanningPdfTests(TestCase):
    @mock.patch("tools.planning_comm_helper.planning_pdf.platform.system", return_value="Windows")
    @mock.patch("tools.planning_comm_helper.planning_pdf._convert_with_windows_excel")
    def test_convert_workbook_to_pdf_uses_windows_excel(
        self,
        convert_with_windows_excel_mock,
        _platform_mock,
    ):
        with tempfile.NamedTemporaryFile(suffix=".xlsx") as workbook:
            convert_with_windows_excel_mock.return_value = Path(workbook.name).with_suffix(".pdf")

            pdf_path = convert_workbook_to_pdf(workbook.name)

        convert_with_windows_excel_mock.assert_called_once()
        self.assertEqual(pdf_path.suffix, ".pdf")

    def test_convert_workbook_to_pdf_rejects_missing_workbook(self):
        with self.assertRaises(PlanningPdfConversionError) as error:
            convert_workbook_to_pdf("/tmp/missing-workbook.xlsx")

        self.assertIn("Workbook not found", str(error.exception))

    def test_build_macos_excel_script_uses_file_reference_without_alias_prompt(self):
        script = excel_pdf._build_macos_excel_script(
            workbook_path=Path("/tmp/example.xlsx"),
            pdf_path=Path("/tmp/example.pdf"),
            strict=True,
        )

        self.assertIn('set workbookFile to POSIX file "/tmp/example.xlsx"', script)
        self.assertIn("open workbook workbook file name workbookFile", script)
        self.assertNotIn("as alias", script)

    @mock.patch("tools.planning_comm_helper.planning_pdf.platform.system", return_value="Linux")
    def test_convert_workbook_to_pdf_rejects_unsupported_platform_without_libreoffice_message(
        self,
        _platform_mock,
    ):
        with tempfile.NamedTemporaryFile(suffix=".xlsx") as workbook:
            with self.assertRaises(PlanningPdfConversionError) as error:
                convert_workbook_to_pdf(workbook.name)

        self.assertNotIn("LibreOffice", str(error.exception))
