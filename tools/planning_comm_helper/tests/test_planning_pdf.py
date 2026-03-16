import sys
import tempfile
import types
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

    @mock.patch("tools.planning_comm_helper.excel_pdf._prepare_windows_workbook_for_export")
    def test_convert_with_windows_excel_initializes_com_for_worker_thread(
        self,
        prepare_windows_workbook_for_export_mock,
    ):
        with tempfile.TemporaryDirectory() as tmpdir:
            workbook_path = Path(tmpdir) / "planning.xlsx"
            workbook_path.write_bytes(b"xlsx-data")
            pdf_path = Path(tmpdir) / "planning.pdf"

            workbook_mock = mock.Mock()

            def _export_as_fixed_format(_format_type, output_path):
                Path(output_path).write_bytes(b"%PDF-1.4 test")

            workbook_mock.ExportAsFixedFormat.side_effect = _export_as_fixed_format
            excel_mock = mock.Mock()
            excel_mock.Workbooks.Open.return_value = workbook_mock

            pythoncom_module = types.ModuleType("pythoncom")
            pythoncom_module.CoInitialize = mock.Mock()
            pythoncom_module.CoUninitialize = mock.Mock()

            win32com_client_module = types.ModuleType("win32com.client")
            win32com_client_module.Dispatch = mock.Mock(return_value=excel_mock)
            win32com_module = types.ModuleType("win32com")
            win32com_module.client = win32com_client_module

            with mock.patch.dict(
                sys.modules,
                {
                    "pythoncom": pythoncom_module,
                    "win32com": win32com_module,
                    "win32com.client": win32com_client_module,
                },
                clear=False,
            ):
                result = excel_pdf._convert_with_windows_excel(workbook_path, pdf_path, strict=True)

        self.assertEqual(result, pdf_path)
        pythoncom_module.CoInitialize.assert_called_once_with()
        pythoncom_module.CoUninitialize.assert_called_once_with()
        win32com_client_module.Dispatch.assert_called_once_with("Excel.Application")
        prepare_windows_workbook_for_export_mock.assert_called_once_with(excel_mock, workbook_mock)
        workbook_mock.Close.assert_called_once_with(False)
        excel_mock.Quit.assert_called_once_with()
