import sys
import tempfile
import types
from pathlib import Path
from unittest import TestCase, mock

from tools.planning_comm_helper.outlook import (
    OutlookPayloadError,
    _open_windows_outlook_draft,
    _materialize_attachments,
    open_outlook_drafts,
)


class PlanningCommunicationHelperOutlookTests(TestCase):
    def test_open_outlook_drafts_validates_required_fields(self):
        with self.assertRaises(OutlookPayloadError):
            open_outlook_drafts(
                [
                    {
                        "recipient_contact": "coordination@example.com",
                        "subject": "",
                        "body_html": "",
                        "attachments": [],
                    }
                ]
            )

    @mock.patch("tools.planning_comm_helper.outlook._open_windows_outlook_draft")
    @mock.patch("tools.planning_comm_helper.outlook.platform.system", return_value="Windows")
    def test_open_outlook_drafts_uses_windows_backend(
        self,
        _platform_mock,
        open_windows_outlook_draft_mock,
    ):
        open_outlook_drafts(
            [
                {
                    "recipient_contact": "coordination@example.com",
                    "subject": "Planning",
                    "body_html": "<p>Bonjour</p>",
                    "attachments": [],
                }
            ]
        )

        open_windows_outlook_draft_mock.assert_called_once()

    @mock.patch("tools.planning_comm_helper.outlook._open_macos_outlook_draft")
    @mock.patch("tools.planning_comm_helper.outlook.platform.system", return_value="Darwin")
    def test_open_outlook_drafts_uses_macos_backend(
        self,
        _platform_mock,
        open_macos_outlook_draft_mock,
    ):
        open_outlook_drafts(
            [
                {
                    "recipient_contact": "coordination@example.com",
                    "subject": "Planning",
                    "body_html": "<p>Bonjour</p>",
                    "attachments": [],
                }
            ]
        )

        open_macos_outlook_draft_mock.assert_called_once()

    @mock.patch("tools.planning_comm_helper.outlook.convert_workbook_to_pdf")
    def test_materialize_attachments_converts_generic_excel_workbook(self, convert_workbook_to_pdf_mock):
        with tempfile.TemporaryDirectory() as temp_dir:
            convert_workbook_to_pdf_mock.return_value = Path(temp_dir) / "planning.pdf"

            _materialize_attachments(
                [
                    {
                        "attachment_type": "excel_workbook",
                        "filename": "planning.xlsx",
                        "content_base64": "eA==",
                    }
                ],
                temp_root=Path(temp_dir),
            )

        convert_workbook_to_pdf_mock.assert_called_once()

    def test_open_windows_outlook_draft_initializes_com_for_worker_thread(self):
        pythoncom_module = types.ModuleType("pythoncom")
        pythoncom_module.CoInitialize = mock.Mock()
        pythoncom_module.CoUninitialize = mock.Mock()

        mail_mock = mock.Mock()
        mail_mock.HTMLBody = "<p>Signature</p>"
        outlook_mock = mock.Mock()
        outlook_mock.CreateItem.return_value = mail_mock

        win32com_client_module = types.ModuleType("win32com.client")
        win32com_client_module.Dispatch = mock.Mock(return_value=outlook_mock)
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
            _open_windows_outlook_draft(
                {
                    "recipient_contact": "coordination@example.com",
                    "subject": "Planning",
                    "body_html": "<p>Bonjour</p>",
                },
                [r"C:\tmp\planning.pdf"],
            )

        pythoncom_module.CoInitialize.assert_called_once_with()
        pythoncom_module.CoUninitialize.assert_called_once_with()
        win32com_client_module.Dispatch.assert_called_once_with("Outlook.Application")
        mail_mock.Attachments.Add.assert_called_once_with(r"C:\tmp\planning.pdf")

    @mock.patch("tools.planning_comm_helper.outlook.convert_workbook_to_pdf")
    def test_materialize_attachments_keeps_legacy_planning_workbook_support(
        self,
        convert_workbook_to_pdf_mock,
    ):
        with tempfile.TemporaryDirectory() as temp_dir:
            convert_workbook_to_pdf_mock.return_value = Path(temp_dir) / "planning.pdf"

            _materialize_attachments(
                [
                    {
                        "attachment_type": "planning_workbook",
                        "filename": "planning.xlsx",
                        "content_base64": "eA==",
                    }
                ],
                temp_root=Path(temp_dir),
            )

        convert_workbook_to_pdf_mock.assert_called_once()
