from types import SimpleNamespace

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, SimpleTestCase

from wms.document_uploads import validate_document_upload
from wms.upload_utils import PORTAL_MAX_FILE_SIZE_MB, validate_upload


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

    def test_validate_upload_accepts_allowed_small_file(self):
        file_obj = SimpleNamespace(name="scan.PDF", size=1024)
        self.assertIsNone(validate_upload(file_obj))


class DocumentUploadsTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.doc_type_choices = [("statutes", "Statuts"), ("other", "Autre")]

    def test_validate_document_upload_rejects_invalid_doc_type(self):
        request = self.factory.post("/portal/account/", data={"doc_type": "unknown"})
        payload, error = validate_document_upload(
            request, doc_type_choices=self.doc_type_choices
        )
        self.assertIsNone(payload)
        self.assertEqual(error, "Type de document invalide.")

    def test_validate_document_upload_requires_file(self):
        request = self.factory.post("/portal/account/", data={"doc_type": "other"})
        payload, error = validate_document_upload(
            request, doc_type_choices=self.doc_type_choices
        )
        self.assertIsNone(payload)
        self.assertEqual(error, "Fichier requis.")

    def test_validate_document_upload_propagates_upload_validation_error(self):
        uploaded = SimpleUploadedFile("notes.txt", b"plain-text")
        request = self.factory.post(
            "/portal/account/",
            data={"doc_type": "other", "doc_file": uploaded},
        )
        payload, error = validate_document_upload(
            request, doc_type_choices=self.doc_type_choices
        )
        self.assertIsNone(payload)
        self.assertEqual(error, "Format non autorise: notes.txt")

    def test_validate_document_upload_accepts_valid_payload(self):
        uploaded = SimpleUploadedFile("piece.pdf", b"pdf-data")
        request = self.factory.post(
            "/portal/account/",
            data={"doc_type": "other", "doc_file": uploaded},
        )
        payload, error = validate_document_upload(
            request, doc_type_choices=self.doc_type_choices
        )
        self.assertIsNone(error)
        self.assertEqual(payload[0], "other")
        self.assertEqual(payload[1].name, "piece.pdf")

    def test_validate_document_upload_supports_custom_file_field(self):
        uploaded = SimpleUploadedFile("proof.jpg", b"jpg-data")
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
