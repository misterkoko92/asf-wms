from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from wms.models import Document, DocumentType, Shipment


class ShipmentDocumentHandlersTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="shipment-doc-user",
            password="pass1234",
            is_staff=True,
        )
        self.client.force_login(self.user)
        self.shipment = Shipment.objects.create(
            shipper_name="Sender",
            recipient_name="Recipient",
            destination_address="1 Rue Test",
            destination_country="France",
            created_by=self.user,
        )
        self.upload_url = reverse(
            "scan:scan_shipment_document_upload",
            kwargs={"shipment_id": self.shipment.id},
        )

    def test_upload_requires_file(self):
        response = self.client.post(self.upload_url, {})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url,
            reverse("scan:scan_shipment_edit", kwargs={"shipment_id": self.shipment.id}),
        )
        self.assertEqual(Document.objects.count(), 0)

    def test_upload_rejects_unsupported_extension(self):
        response = self.client.post(
            self.upload_url,
            {"document_file": SimpleUploadedFile("notes.txt", b"text")},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Document.objects.count(), 0)

    def test_upload_creates_additional_document_when_file_is_valid(self):
        response = self.client.post(
            self.upload_url,
            {"document_file": SimpleUploadedFile("attestation.pdf", b"pdf")},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Document.objects.count(), 1)
        document = Document.objects.get()
        self.assertEqual(document.shipment_id, self.shipment.id)
        self.assertEqual(document.doc_type, DocumentType.ADDITIONAL)
        self.assertTrue(document.file.name.endswith(".pdf"))

    def test_delete_removes_additional_document(self):
        document = Document.objects.create(
            shipment=self.shipment,
            doc_type=DocumentType.ADDITIONAL,
            file=SimpleUploadedFile("delete.pdf", b"pdf"),
        )
        delete_url = reverse(
            "scan:scan_shipment_document_delete",
            kwargs={"shipment_id": self.shipment.id, "document_id": document.id},
        )
        response = self.client.post(delete_url, {})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Document.objects.filter(id=document.id).exists())

    def test_delete_rejects_non_additional_document(self):
        document = Document.objects.create(
            shipment=self.shipment,
            doc_type=DocumentType.SHIPMENT_NOTE,
            file=SimpleUploadedFile("locked.pdf", b"pdf"),
        )
        delete_url = reverse(
            "scan:scan_shipment_document_delete",
            kwargs={"shipment_id": self.shipment.id, "document_id": document.id},
        )
        response = self.client.post(delete_url, {})
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Document.objects.filter(id=document.id).exists())
