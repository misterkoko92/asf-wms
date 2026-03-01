from types import SimpleNamespace

from django.test import TestCase

from wms.print_pack_engine import PrintPackEngineError
from wms.print_pack_xlsx import (
    XLSX_CONTENT_TYPE,
    ZIP_CONTENT_TYPE,
    build_xlsx_fallback_response,
)


class PrintPackXlsxTests(TestCase):
    def test_build_xlsx_fallback_response_returns_single_xlsx_attachment(self):
        documents = [SimpleNamespace(filename="A-picking.xlsx", payload=b"xlsx-bytes")]

        response = build_xlsx_fallback_response(documents=documents, pack_code="A")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], XLSX_CONTENT_TYPE)
        self.assertIn("A-picking.xlsx", response["Content-Disposition"])
        self.assertEqual(response.content, b"xlsx-bytes")
        self.assertEqual(response["X-WMS-Print-Mode"], "xlsx-fallback")

    def test_build_xlsx_fallback_response_returns_zip_for_multiple_documents(self):
        documents = [
            SimpleNamespace(filename="B-1.xlsx", payload=b"xlsx-1"),
            SimpleNamespace(filename="B-2.xlsx", payload=b"xlsx-2"),
        ]

        response = build_xlsx_fallback_response(documents=documents, pack_code="B")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], ZIP_CONTENT_TYPE)
        self.assertIn("print-pack-B-", response["Content-Disposition"])
        self.assertTrue(response.content.startswith(b"PK"))
        self.assertEqual(response["X-WMS-Print-Mode"], "xlsx-fallback")

    def test_build_xlsx_fallback_response_raises_when_documents_are_missing(self):
        with self.assertRaises(PrintPackEngineError):
            build_xlsx_fallback_response(documents=[], pack_code="A")
