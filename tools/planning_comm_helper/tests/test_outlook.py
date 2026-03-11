from unittest import TestCase, mock

from tools.planning_comm_helper.outlook import OutlookPayloadError, open_outlook_drafts


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
