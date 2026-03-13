from unittest import TestCase, mock

from tools.planning_comm_helper.server import (
    HELPER_HEADER,
    HelperRequestError,
    build_cors_headers,
    handle_json_request,
)


class PlanningCommunicationHelperServerTests(TestCase):
    def test_build_cors_headers_allows_private_network_preflight(self):
        headers = build_cors_headers(
            origin="https://example.com",
            request_private_network=True,
        )

        self.assertEqual(headers["Access-Control-Allow-Origin"], "https://example.com")
        self.assertEqual(headers["Access-Control-Allow-Private-Network"], "true")
        self.assertIn(HELPER_HEADER, headers["Access-Control-Allow-Headers"])

    @mock.patch("tools.planning_comm_helper.server.get_helper_runtime_metadata")
    def test_handle_json_request_returns_helper_health_metadata(self, metadata_mock):
        metadata_mock.return_value = {
            "helper_version": "0.1.0",
            "platform": "Darwin",
            "capabilities": ["pdf_render", "excel_render", "pdf_merge"],
        }

        response = handle_json_request(
            method="POST",
            path="/health",
            headers={HELPER_HEADER: "1"},
            payload={},
        )

        self.assertEqual(
            response,
            {
                "ok": True,
                "helper_version": "0.1.0",
                "platform": "Darwin",
                "capabilities": ["pdf_render", "excel_render", "pdf_merge"],
            },
        )

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

    def test_handle_json_request_validates_pdf_render_payload(self):
        with self.assertRaises(HelperRequestError) as error:
            handle_json_request(
                method="POST",
                path="/v1/pdf/render",
                headers={HELPER_HEADER: "1"},
                payload={"output_filename": "planning.pdf"},
            )

        self.assertEqual(error.exception.status_code, 422)

    def test_handle_json_request_validates_pdf_render_document_shape(self):
        with self.assertRaises(HelperRequestError) as error:
            handle_json_request(
                method="POST",
                path="/v1/pdf/render",
                headers={HELPER_HEADER: "1"},
                payload={
                    "documents": [{"filename": "", "content_base64": ""}],
                    "output_filename": "planning.pdf",
                },
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

    @mock.patch("tools.planning_comm_helper.server.render_pdf_job", create=True)
    def test_handle_json_request_dispatches_pdf_render_job(self, render_pdf_job_mock):
        render_pdf_job_mock.return_value = {
            "ok": True,
            "output_filename": "planning.pdf",
            "opened": True,
            "warning_messages": [],
        }
        response = handle_json_request(
            method="POST",
            path="/v1/pdf/render",
            headers={HELPER_HEADER: "1"},
            payload={
                "documents": [
                    {
                        "filename": "planning.xlsx",
                        "content_base64": "eA==",
                    }
                ],
                "output_filename": "planning.pdf",
                "open_after_render": True,
            },
        )

        render_pdf_job_mock.assert_called_once()
        self.assertEqual(response["output_filename"], "planning.pdf")
        self.assertTrue(response["opened"])
