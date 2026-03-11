from unittest import TestCase, mock

from tools.planning_comm_helper.server import (
    HELPER_HEADER,
    HelperRequestError,
    handle_json_request,
)


class PlanningCommunicationHelperServerTests(TestCase):
    def test_handle_json_request_rejects_unsupported_route(self):
        with self.assertRaises(HelperRequestError) as error:
            handle_json_request(
                method="POST",
                path="/v1/unknown",
                headers={HELPER_HEADER: "1"},
                payload={},
            )

        self.assertEqual(error.exception.status_code, 404)

    def test_handle_json_request_validates_whatsapp_payload(self):
        with self.assertRaises(HelperRequestError) as error:
            handle_json_request(
                method="POST",
                path="/v1/whatsapp/open",
                headers={HELPER_HEADER: "1"},
                payload={"drafts": [{"recipient_contact": "", "body": ""}]},
            )

        self.assertEqual(error.exception.status_code, 422)

    @mock.patch("tools.planning_comm_helper.server.open_whatsapp_drafts")
    def test_handle_json_request_dispatches_whatsapp_drafts(self, open_whatsapp_drafts_mock):
        open_whatsapp_drafts_mock.return_value = 1
        response = handle_json_request(
            method="POST",
            path="/v1/whatsapp/open",
            headers={HELPER_HEADER: "1"},
            payload={"drafts": [{"recipient_contact": "0611223344", "body": "Bonjour"}]},
        )

        open_whatsapp_drafts_mock.assert_called_once()
        self.assertEqual(response["opened_count"], 1)

    @mock.patch("tools.planning_comm_helper.server.open_outlook_drafts")
    def test_handle_json_request_dispatches_email_drafts(self, open_outlook_drafts_mock):
        open_outlook_drafts_mock.return_value = 1
        response = handle_json_request(
            method="POST",
            path="/v1/outlook/open",
            headers={HELPER_HEADER: "1"},
            payload={
                "drafts": [
                    {
                        "recipient_contact": "coordination@example.com",
                        "subject": "Planning semaine 11",
                        "body_html": "<p>Bonjour</p>",
                        "attachments": [],
                    }
                ]
            },
        )

        open_outlook_drafts_mock.assert_called_once()
        self.assertEqual(response["opened_count"], 1)
