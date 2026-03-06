import json
from io import BytesIO
from unittest import mock
from urllib import error

from django.test import SimpleTestCase, override_settings

from wms.print_pack_graph import (
    GraphPdfConversionError,
    _decode_http_error,
    _download_pdf_export,
    _graph_export_pdf,
    _request_graph_token,
    _upload_workbook_item,
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
        with (
            mock.patch(
                "wms.print_pack_graph.get_client_credentials_token",
                return_value="graph-token",
            ) as token_mock,
            mock.patch(
                "wms.print_pack_graph._graph_export_pdf",
                return_value=b"%PDF-1.4 sample",
            ) as export_mock,
        ):
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
        with (
            mock.patch(
                "wms.print_pack_graph.get_client_credentials_token",
                return_value="graph-token",
            ),
            mock.patch(
                "wms.print_pack_graph._graph_export_pdf",
                return_value=b"not-a-pdf",
            ),
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

    @override_settings(GRAPH_DRIVE_ID="drive-123")
    def test_graph_export_pdf_uploads_converts_and_cleans_up(self):
        responses = {
            "PUT": self._UrlOpenResponse(json.dumps({"id": "item-42"}).encode("utf-8")),
            "GET": self._UrlOpenResponse(b"%PDF-1.7 test"),
            "DELETE": self._UrlOpenResponse(b"", status=204),
        }
        captured_methods = []

        def _fake_urlopen(req, timeout):  # noqa: ARG001
            method = req.get_method()
            captured_methods.append(method)
            return responses[method]

        with mock.patch("wms.print_pack_graph.request.urlopen", side_effect=_fake_urlopen):
            pdf_bytes = _graph_export_pdf(
                token="token",
                xlsx_bytes=b"xlsx-data",
                filename="pack-b.xlsx",
                timeout=12,
            )

        self.assertEqual(pdf_bytes, b"%PDF-1.7 test")
        self.assertEqual(captured_methods, ["PUT", "GET", "DELETE"])

    @override_settings(GRAPH_DRIVE_ID="")
    def test_graph_export_pdf_raises_when_drive_id_is_missing(self):
        with self.assertRaises(GraphPdfConversionError):
            _graph_export_pdf(
                token="token",
                xlsx_bytes=b"xlsx-data",
                filename="pack-b.xlsx",
                timeout=12,
            )

    @override_settings(GRAPH_DRIVE_ID="drive-123")
    def test_graph_export_pdf_raises_when_upload_response_has_no_item_id(self):
        with mock.patch(
            "wms.print_pack_graph.request.urlopen",
            return_value=self._UrlOpenResponse(json.dumps({}).encode("utf-8")),
        ):
            with self.assertRaises(GraphPdfConversionError):
                _graph_export_pdf(
                    token="token",
                    xlsx_bytes=b"xlsx-data",
                    filename="pack-b.xlsx",
                    timeout=12,
                )

    def test_decode_http_error_returns_message_for_non_http_error(self):
        message = _decode_http_error(ValueError("boom"))
        self.assertEqual(message, "boom")

    def test_decode_http_error_falls_back_to_exception_string_when_body_unreadable(self):
        exc = error.HTTPError(
            url="https://graph.microsoft.com/v1.0/test",
            code=500,
            msg="server error",
            hdrs=None,
            fp=None,
        )
        exc.read = mock.Mock(side_effect=OSError("read failed"))

        message = _decode_http_error(exc)

        self.assertIn("HTTP Error 500", message)

    @override_settings(GRAPH_DRIVE_ID="drive-123")
    def test_upload_workbook_item_raises_graph_error_on_http_error(self):
        http_error = error.HTTPError(
            url="https://graph.microsoft.com/v1.0/drives/drive-123/root:/tmp/content",
            code=429,
            msg="Too Many Requests",
            hdrs=None,
            fp=BytesIO(b'{"error":"rate_limited"}'),
        )
        with mock.patch("wms.print_pack_graph.request.urlopen", side_effect=http_error):
            with self.assertRaises(GraphPdfConversionError) as exc:
                _upload_workbook_item(
                    token="token",
                    drive_id="drive-123",
                    xlsx_bytes=b"xlsx-data",
                    filename="pack-b.xlsx",
                    timeout=10,
                )

        self.assertIn("HTTP 429", str(exc.exception))
        self.assertIn("rate_limited", str(exc.exception))

    @override_settings(GRAPH_DRIVE_ID="drive-123")
    def test_upload_workbook_item_raises_graph_error_on_url_error(self):
        with mock.patch(
            "wms.print_pack_graph.request.urlopen",
            side_effect=error.URLError("network down"),
        ):
            with self.assertRaises(GraphPdfConversionError):
                _upload_workbook_item(
                    token="token",
                    drive_id="drive-123",
                    xlsx_bytes=b"xlsx-data",
                    filename="pack-b.xlsx",
                    timeout=10,
                )

    @override_settings(GRAPH_DRIVE_ID="drive-123")
    def test_upload_workbook_item_raises_on_invalid_json_payload(self):
        with mock.patch(
            "wms.print_pack_graph.request.urlopen",
            return_value=self._UrlOpenResponse(b"not-json"),
        ):
            with self.assertRaises(GraphPdfConversionError):
                _upload_workbook_item(
                    token="token",
                    drive_id="drive-123",
                    xlsx_bytes=b"xlsx-data",
                    filename="pack-b.xlsx",
                    timeout=10,
                )

    @override_settings(GRAPH_DRIVE_ID="drive-123")
    def test_download_pdf_export_raises_graph_error_on_http_error(self):
        http_error = error.HTTPError(
            url="https://graph.microsoft.com/v1.0/drives/drive-123/items/item-42/content?format=pdf",
            code=500,
            msg="server error",
            hdrs=None,
            fp=BytesIO(b"graph-error"),
        )
        with mock.patch("wms.print_pack_graph.request.urlopen", side_effect=http_error):
            with self.assertRaises(GraphPdfConversionError) as exc:
                _download_pdf_export(
                    token="token",
                    drive_id="drive-123",
                    item_id="item-42",
                    timeout=10,
                )

        self.assertIn("HTTP 500", str(exc.exception))

    @override_settings(GRAPH_DRIVE_ID="drive-123")
    def test_download_pdf_export_raises_graph_error_on_url_error(self):
        with mock.patch(
            "wms.print_pack_graph.request.urlopen",
            side_effect=error.URLError("network down"),
        ):
            with self.assertRaises(GraphPdfConversionError):
                _download_pdf_export(
                    token="token",
                    drive_id="drive-123",
                    item_id="item-42",
                    timeout=10,
                )
