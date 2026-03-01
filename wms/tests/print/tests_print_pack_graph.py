import json
from unittest import mock
from urllib import error

from django.test import SimpleTestCase, override_settings

from wms.print_pack_graph import (
    GraphPdfConversionError,
    _graph_export_pdf,
    _request_graph_token,
    _validate_https_url,
    convert_excel_to_pdf_via_graph,
    get_client_credentials_token,
)


class PrintPackGraphTests(SimpleTestCase):
    class _UrlOpenResponse:
        def __init__(self, body, status=200):
            self._body = body
            self.status = status

        def read(self):
            return self._body

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

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

    def test_validate_https_url_rejects_non_https(self):
        with self.assertRaises(GraphPdfConversionError):
            _validate_https_url("http://example.org/token")

    def test_request_graph_token_returns_access_token(self):
        payload = json.dumps({"access_token": "token-123"}).encode("utf-8")
        with mock.patch(
            "wms.print_pack_graph.request.urlopen",
            return_value=self._UrlOpenResponse(payload),
        ) as urlopen_mock:
            token = _request_graph_token(
                tenant_id="tenant",
                client_id="client",
                client_secret="secret",
                timeout=15,
            )
        self.assertEqual(token, "token-123")
        request_obj = urlopen_mock.call_args.args[0]
        self.assertEqual(
            request_obj.full_url,
            "https://login.microsoftonline.com/tenant/oauth2/v2.0/token",
        )

    def test_request_graph_token_raises_on_invalid_json_payload(self):
        with mock.patch(
            "wms.print_pack_graph.request.urlopen",
            return_value=self._UrlOpenResponse(b"not-json"),
        ):
            with self.assertRaises(GraphPdfConversionError):
                _request_graph_token(
                    tenant_id="tenant",
                    client_id="client",
                    client_secret="secret",
                    timeout=10,
                )

    def test_request_graph_token_raises_on_missing_access_token(self):
        payload = json.dumps({"token_type": "Bearer"}).encode("utf-8")
        with mock.patch(
            "wms.print_pack_graph.request.urlopen",
            return_value=self._UrlOpenResponse(payload),
        ):
            with self.assertRaises(GraphPdfConversionError):
                _request_graph_token(
                    tenant_id="tenant",
                    client_id="client",
                    client_secret="secret",
                    timeout=10,
                )

    def test_request_graph_token_raises_on_url_error(self):
        with mock.patch(
            "wms.print_pack_graph.request.urlopen",
            side_effect=error.URLError("network down"),
        ):
            with self.assertRaises(GraphPdfConversionError):
                _request_graph_token(
                    tenant_id="tenant",
                    client_id="client",
                    client_secret="secret",
                    timeout=10,
                )

    def test_convert_excel_to_pdf_via_graph_rejects_empty_excel_payload(self):
        with self.assertRaises(GraphPdfConversionError):
            convert_excel_to_pdf_via_graph(xlsx_bytes=b"", filename="pack-b.xlsx")

    def test_convert_excel_to_pdf_via_graph_rejects_missing_filename(self):
        with self.assertRaises(GraphPdfConversionError):
            convert_excel_to_pdf_via_graph(xlsx_bytes=b"xlsx-data", filename="")

    def test_graph_export_pdf_placeholder_raises(self):
        with self.assertRaises(GraphPdfConversionError):
            _graph_export_pdf(
                token="token",
                xlsx_bytes=b"xlsx-data",
                filename="pack-b.xlsx",
                timeout=12,
            )
