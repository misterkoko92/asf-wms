import tempfile
from pathlib import Path
from unittest import TestCase, mock

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

    @mock.patch("tools.planning_comm_helper.planning_pdf.platform.system", return_value="Linux")
    def test_convert_workbook_to_pdf_refuses_libreoffice_fallback(self, _platform_mock):
        with tempfile.NamedTemporaryFile(suffix=".xlsx") as workbook:
            with self.assertRaises(PlanningPdfConversionError) as error:
                convert_workbook_to_pdf(workbook.name)

        self.assertIn("LibreOffice fallback is not supported", str(error.exception))
