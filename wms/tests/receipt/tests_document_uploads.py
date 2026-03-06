from types import SimpleNamespace

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, SimpleTestCase

from wms.document_uploads import validate_document_upload
from wms.upload_utils import (
    PORTAL_MAX_FILE_SIZE_MB,
    _has_valid_file_signature,
    _read_file_header,
    validate_upload,
)


class UploadUtilsTests(SimpleTestCase):
    def test_validate_upload_rejects_unsupported_extension(self):
        file_obj = SimpleNamespace(name="notes.txt", size=10)
        error = validate_upload(file_obj)
        self.assertEqual(error, "Format non autorise: notes.txt")

    def test_validate_upload_rejects_file_too_large(self):
        max_bytes = PORTAL_MAX_FILE_SIZE_MB * 1024 * 1024
        file_obj = SimpleNamespace(name="scan.pdf", size=max_bytes + 1)
        error = validate_upload(file_obj)
        self.assertEqual(error, "Fichier trop volumineux: scan.pdf")

    def test_validate_upload_rejects_mismatched_file_content(self):
        file_obj = SimpleUploadedFile("scan.pdf", b"plain-text-content")
        error = validate_upload(file_obj)
        self.assertEqual(error, "Contenu de fichier invalide: scan.pdf")

    def test_validate_upload_accepts_allowed_small_file(self):
        file_obj = SimpleUploadedFile("scan.PDF", b"%PDF-1.7 sample")
        self.assertIsNone(validate_upload(file_obj))

    def test_validate_upload_accepts_zip_based_office_signature(self):
        file_obj = SimpleUploadedFile("report.docx", b"PK\x03\x04content")
        self.assertIsNone(validate_upload(file_obj))

    def test_validate_upload_rejects_mismatched_office_signature(self):
        file_obj = SimpleUploadedFile("report.docx", b"%PDF-1.4 wrong")
        error = validate_upload(file_obj)
        self.assertEqual(error, "Contenu de fichier invalide: report.docx")

    def test_read_file_header_handles_non_seekable_string_readers(self):
        class StringReader:
            def read(self, _length):
                return "abc"

        self.assertEqual(_read_file_header(StringReader(), 3), b"abc")

    def test_read_file_header_restores_cursor_position(self):
        file_obj = SimpleUploadedFile("piece.pdf", b"%PDF-1.4 data")
        file_obj.seek(5)

        header = _read_file_header(file_obj, 5)

        self.assertEqual(header, b"1.4 d")
        self.assertEqual(file_obj.tell(), 5)

    def test_has_valid_file_signature_returns_true_for_unknown_suffix(self):
        file_obj = SimpleUploadedFile("binary.bin", b"\x00\x01\x02")
        self.assertTrue(_has_valid_file_signature(file_obj, ".bin"))

    def test_read_file_header_returns_empty_when_reader_missing(self):
        file_obj = SimpleNamespace()
        self.assertEqual(_read_file_header(file_obj, 10), b"")

    def test_read_file_header_handles_reader_exceptions(self):
        class BrokenReader:
            def tell(self):
                return 0

            def read(self, _length):
                raise OSError("boom")

            def seek(self, _position):
                return None

        self.assertEqual(_read_file_header(BrokenReader(), 10), b"")

    def test_read_file_header_ignores_tell_and_seek_failures(self):
        class BrokenPositionReader:
            def tell(self):
                raise RuntimeError("tell failed")

            def read(self, _length):
                return b"%PDF-1.7"

            def seek(self, _position):
                raise RuntimeError("seek failed")

        self.assertEqual(_read_file_header(BrokenPositionReader(), 8), b"%PDF-1.7")

    def test_has_valid_file_signature_rejects_empty_header_for_known_suffix(self):
        file_obj = SimpleUploadedFile("scan.pdf", b"")
        self.assertFalse(_has_valid_file_signature(file_obj, ".pdf"))


class DocumentUploadsTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.doc_type_choices = [("statutes", "Statuts"), ("other", "Autre")]

    def test_validate_document_upload_rejects_invalid_doc_type(self):
        request = self.factory.post("/portal/account/", data={"doc_type": "unknown"})
        payload, error = validate_document_upload(request, doc_type_choices=self.doc_type_choices)
        self.assertIsNone(payload)
        self.assertEqual(error, "Type de document invalide.")

    def test_validate_document_upload_requires_file(self):
        request = self.factory.post("/portal/account/", data={"doc_type": "other"})
        payload, error = validate_document_upload(request, doc_type_choices=self.doc_type_choices)
        self.assertIsNone(payload)
        self.assertEqual(error, "Fichier requis.")

    def test_validate_document_upload_propagates_upload_validation_error(self):
        uploaded = SimpleUploadedFile("notes.txt", b"plain-text")
        request = self.factory.post(
            "/portal/account/",
            data={"doc_type": "other", "doc_file": uploaded},
        )
        payload, error = validate_document_upload(request, doc_type_choices=self.doc_type_choices)
        self.assertIsNone(payload)
        self.assertEqual(error, "Format non autorise: notes.txt")

    def test_validate_document_upload_accepts_valid_payload(self):
        uploaded = SimpleUploadedFile("piece.pdf", b"%PDF-1.4 valid")
        request = self.factory.post(
            "/portal/account/",
            data={"doc_type": "other", "doc_file": uploaded},
        )
        payload, error = validate_document_upload(request, doc_type_choices=self.doc_type_choices)
        self.assertIsNone(error)
        self.assertEqual(payload[0], "other")
        self.assertEqual(payload[1].name, "piece.pdf")

    def test_validate_document_upload_supports_custom_file_field(self):
        uploaded = SimpleUploadedFile("proof.jpg", b"\xff\xd8\xff\xe0jpg-data")
        request = self.factory.post(
            "/portal/account/",
            data={"doc_type": "statutes", "attachment": uploaded},
        )
        payload, error = validate_document_upload(
            request,
            doc_type_choices=self.doc_type_choices,
            file_field="attachment",
        )
        self.assertIsNone(error)
        self.assertEqual(payload[0], "statutes")
        self.assertEqual(payload[1].name, "proof.jpg")
