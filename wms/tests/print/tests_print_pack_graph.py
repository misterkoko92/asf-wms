from unittest import mock

from django.test import SimpleTestCase, override_settings

from wms.print_pack_graph import (
    GraphPdfConversionError,
    convert_excel_to_pdf_via_graph,
    get_client_credentials_token,
)


class PrintPackGraphTests(SimpleTestCase):
    @override_settings(
        GRAPH_TENANT_ID="tenant-id",
        GRAPH_CLIENT_ID="client-id",
        GRAPH_CLIENT_SECRET="client-secret",
    )
    def test_get_client_credentials_token_delegates_to_token_request(self):
        with mock.patch(
            "wms.print_pack_graph._request_graph_token",
            return_value="test-token",
        ) as request_mock:
            token = get_client_credentials_token(timeout=21)

        self.assertEqual(token, "test-token")
        request_mock.assert_called_once_with(
            tenant_id="tenant-id",
            client_id="client-id",
            client_secret="client-secret",
            timeout=21,
        )

    @override_settings(
        GRAPH_TENANT_ID="",
        GRAPH_CLIENT_ID="",
        GRAPH_CLIENT_SECRET="",
    )
    def test_get_client_credentials_token_raises_when_settings_are_missing(self):
        with self.assertRaises(GraphPdfConversionError):
            get_client_credentials_token()

    def test_convert_excel_to_pdf_via_graph_returns_pdf_bytes(self):
        with mock.patch(
            "wms.print_pack_graph.get_client_credentials_token",
            return_value="graph-token",
        ) as token_mock, mock.patch(
            "wms.print_pack_graph._graph_export_pdf",
            return_value=b"%PDF-1.4 sample",
        ) as export_mock:
            pdf_bytes = convert_excel_to_pdf_via_graph(
                xlsx_bytes=b"xlsx-data",
                filename="pack-b.xlsx",
                timeout=33,
            )

        self.assertTrue(pdf_bytes.startswith(b"%PDF"))
        token_mock.assert_called_once_with(timeout=33)
        export_mock.assert_called_once_with(
            token="graph-token",
            xlsx_bytes=b"xlsx-data",
            filename="pack-b.xlsx",
            timeout=33,
        )

    def test_convert_excel_to_pdf_via_graph_rejects_non_pdf_payload(self):
        with mock.patch(
            "wms.print_pack_graph.get_client_credentials_token",
            return_value="graph-token",
        ), mock.patch(
            "wms.print_pack_graph._graph_export_pdf",
            return_value=b"not-a-pdf",
        ):
            with self.assertRaises(GraphPdfConversionError):
                convert_excel_to_pdf_via_graph(
                    xlsx_bytes=b"xlsx-data",
                    filename="pack-b.xlsx",
                )
