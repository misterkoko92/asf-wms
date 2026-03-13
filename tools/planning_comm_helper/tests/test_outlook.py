import tempfile
from pathlib import Path
from unittest import TestCase, mock

from tools.planning_comm_helper.outlook import (
    OutlookPayloadError,
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
