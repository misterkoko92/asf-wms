import tempfile
from io import StringIO
from types import SimpleNamespace
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings

from wms.document_scan import DocumentScanStatus
from wms import document_scan_queue as queue_module
from wms.document_scan_queue import (
    process_document_scan_queue,
    queue_document_scan,
)
from wms.models import (
    AccountDocument,
    AccountDocumentType,
    IntegrationDirection,
    IntegrationEvent,
    IntegrationStatus,
)


class DocumentScanQueueTests(TestCase):
    def _create_account_document(self):
        return AccountDocument.objects.create(
            doc_type=AccountDocumentType.OTHER,
            file=SimpleUploadedFile("queue.pdf", b"%PDF-1.4 queue"),
            scan_status=DocumentScanStatus.PENDING,
            scan_message="Scan antivirus en cours.",
        )

    def test_queue_document_scan_creates_pending_event(self):
        document = self._create_account_document()

        queued = queue_document_scan(document)

        self.assertTrue(queued)
        event = IntegrationEvent.objects.get()
        self.assertEqual(event.direction, IntegrationDirection.OUTBOUND)
        self.assertEqual(event.source, "wms.document_scan")
        self.assertEqual(event.event_type, "scan_document")
        self.assertEqual(event.status, IntegrationStatus.PENDING)
        self.assertEqual(event.payload["model"], "wms.AccountDocument")
        self.assertEqual(event.payload["pk"], document.id)

    def test_queue_document_scan_rejects_invalid_inputs(self):
        self.assertFalse(queue_document_scan(None))
        self.assertFalse(queue_document_scan(SimpleNamespace(pk=None, file=object())))
        self.assertFalse(queue_document_scan(SimpleNamespace(pk=1, file=None)))

    def test_numeric_and_backend_helpers(self):
        self.assertEqual(queue_module._safe_int("7", default=3, minimum=1), 7)
        self.assertEqual(queue_module._safe_int("0", default=3, minimum=1), 1)
        self.assertEqual(queue_module._safe_int("x", default=3, minimum=1), 3)
        self.assertEqual(queue_module._coerce_limit("0"), 1)
        self.assertEqual(queue_module._processing_timeout_seconds("0"), 1)
        self.assertEqual(queue_module._candidate_statuses(False), [IntegrationStatus.PENDING])
        self.assertEqual(
            queue_module._candidate_statuses(True),
            [IntegrationStatus.PENDING, IntegrationStatus.FAILED],
        )

    @override_settings(DOCUMENT_SCAN_BACKEND="noop")
    def test_scan_backend_accepts_noop(self):
        self.assertEqual(queue_module._scan_backend(), queue_module.DOCUMENT_SCAN_BACKEND_NOOP)

    @override_settings(DOCUMENT_SCAN_BACKEND="invalid")
    def test_scan_backend_falls_back_to_clamav(self):
        self.assertEqual(
            queue_module._scan_backend(),
            queue_module.DOCUMENT_SCAN_BACKEND_CLAMAV,
        )

    @override_settings(DOCUMENT_SCAN_CLAMAV_COMMAND="")
    def test_clamav_command_falls_back_to_default(self):
        self.assertEqual(queue_module._clamav_command(), "clamscan")

    @override_settings(DOCUMENT_SCAN_TIMEOUT_SECONDS="2")
    def test_scan_timeout_seconds_has_minimum_floor(self):
        self.assertEqual(queue_module._scan_timeout_seconds(), 5)

    @mock.patch("wms.document_scan_queue.subprocess.run")
    def test_scan_file_with_clamav_maps_return_codes(self, run_mock):
        run_mock.return_value = SimpleNamespace(returncode=0, stdout="OK", stderr="")
        status, message = queue_module._scan_file_with_clamav("/tmp/file.pdf")
        self.assertEqual(status, DocumentScanStatus.CLEAN)
        self.assertEqual(message, "OK")

        run_mock.return_value = SimpleNamespace(returncode=1, stdout="", stderr="")
        status, message = queue_module._scan_file_with_clamav("/tmp/file.pdf")
        self.assertEqual(status, DocumentScanStatus.INFECTED)
        self.assertEqual(message, "Fichier infecté détecté.")

        run_mock.return_value = SimpleNamespace(returncode=2, stdout="", stderr="")
        status, message = queue_module._scan_file_with_clamav("/tmp/file.pdf")
        self.assertEqual(status, DocumentScanStatus.ERROR)
        self.assertEqual(message, "Erreur inconnue du scan antivirus.")

    @mock.patch("wms.document_scan_queue.subprocess.run", side_effect=FileNotFoundError)
    def test_scan_file_with_clamav_handles_command_not_found(self, _run_mock):
        status, message = queue_module._scan_file_with_clamav("/tmp/file.pdf")
        self.assertEqual(status, DocumentScanStatus.ERROR)
        self.assertEqual(message, "Commande ClamAV introuvable.")

    @mock.patch(
        "wms.document_scan_queue.subprocess.run",
        side_effect=queue_module.subprocess.TimeoutExpired(cmd="clamscan", timeout=1),
    )
    def test_scan_file_with_clamav_handles_timeout(self, _run_mock):
        status, message = queue_module._scan_file_with_clamav("/tmp/file.pdf")
        self.assertEqual(status, DocumentScanStatus.ERROR)
        self.assertEqual(message, "Scan antivirus expiré.")

    def test_scan_uploaded_file_covers_error_paths(self):
        self.assertEqual(
            queue_module.scan_uploaded_file(None),
            (DocumentScanStatus.ERROR, "Fichier absent."),
        )

        class NoPathFile:
            @property
            def path(self):
                raise RuntimeError("no path")

        self.assertEqual(
            queue_module.scan_uploaded_file(NoPathFile()),
            (
                DocumentScanStatus.ERROR,
                "Stockage non local: chemin fichier indisponible pour scan.",
            ),
        )

        self.assertEqual(
            queue_module.scan_uploaded_file(SimpleNamespace(path="")),
            (DocumentScanStatus.ERROR, "Chemin fichier indisponible."),
        )
        self.assertEqual(
            queue_module.scan_uploaded_file(SimpleNamespace(path="/tmp/file-does-not-exist.pdf")),
            (DocumentScanStatus.ERROR, "Fichier introuvable."),
        )

    @override_settings(DOCUMENT_SCAN_BACKEND="noop")
    def test_scan_uploaded_file_supports_noop_backend(self):
        with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp:
            status, message = queue_module.scan_uploaded_file(SimpleNamespace(path=tmp.name))
        self.assertEqual(status, DocumentScanStatus.CLEAN)
        self.assertEqual(message, "Scan noop (backend de test).")

    @mock.patch("wms.document_scan_queue._scan_file_with_clamav")
    @override_settings(DOCUMENT_SCAN_BACKEND="clamav")
    def test_scan_uploaded_file_delegates_to_clamav_backend(self, scan_mock):
        scan_mock.return_value = (DocumentScanStatus.CLEAN, "clean")
        with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp:
            status, message = queue_module.scan_uploaded_file(SimpleNamespace(path=tmp.name))
        self.assertEqual(status, DocumentScanStatus.CLEAN)
        self.assertEqual(message, "clean")
        scan_mock.assert_called_once()

    def test_resolve_document_instance_validates_payload(self):
        self.assertEqual(
            queue_module._resolve_document_instance("invalid"),
            (None, "Payload de scan invalide."),
        )
        self.assertEqual(
            queue_module._resolve_document_instance({"pk": 1}),
            (None, "Payload sans modèle de document."),
        )
        self.assertEqual(
            queue_module._resolve_document_instance({"model": "wms.AccountDocument"}),
            (None, "Payload sans identifiant document."),
        )

    @mock.patch("wms.document_scan_queue.apps.get_model", return_value=None)
    def test_resolve_document_instance_handles_missing_model(self, _get_model_mock):
        document_obj, error = queue_module._resolve_document_instance(
            {"model": "wms.Unknown", "pk": 1}
        )
        self.assertIsNone(document_obj)
        self.assertEqual(error, "Modèle document introuvable: wms.Unknown.")

    @mock.patch("wms.document_scan_queue.apps.get_model", side_effect=LookupError("bad model"))
    def test_resolve_document_instance_handles_unknown_model_label(self, _get_model_mock):
        document_obj, error = queue_module._resolve_document_instance(
            {"model": "wms.Bad", "pk": 1}
        )
        self.assertIsNone(document_obj)
        self.assertEqual(error, "Modèle document inconnu: wms.Bad.")

    @mock.patch("wms.document_scan_queue.scan_uploaded_file")
    def test_process_document_scan_queue_marks_document_clean(self, scan_mock):
        scan_mock.return_value = (DocumentScanStatus.CLEAN, "clean")
        document = self._create_account_document()
        queue_document_scan(document)

        result = process_document_scan_queue(limit=10)

        self.assertEqual(
            result,
            {"selected": 1, "processed": 1, "infected": 0, "failed": 0},
        )
        document.refresh_from_db()
        self.assertEqual(document.scan_status, DocumentScanStatus.CLEAN)
        self.assertEqual(document.scan_message, "clean")
        self.assertIsNotNone(document.scan_updated_at)
        event = IntegrationEvent.objects.get()
        self.assertEqual(event.status, IntegrationStatus.PROCESSED)
        self.assertEqual(event.payload["scan_status"], DocumentScanStatus.CLEAN)

    @mock.patch("wms.document_scan_queue.scan_uploaded_file")
    def test_process_document_scan_queue_marks_document_infected(self, scan_mock):
        scan_mock.return_value = (DocumentScanStatus.INFECTED, "infected")
        document = self._create_account_document()
        queue_document_scan(document)

        result = process_document_scan_queue(limit=10)

        self.assertEqual(
            result,
            {"selected": 1, "processed": 0, "infected": 1, "failed": 0},
        )
        document.refresh_from_db()
        self.assertEqual(document.scan_status, DocumentScanStatus.INFECTED)
        self.assertEqual(document.scan_message, "infected")
        event = IntegrationEvent.objects.get()
        self.assertEqual(event.status, IntegrationStatus.PROCESSED)
        self.assertIn("Fichier infecté", event.error_message)

    def test_process_document_scan_queue_marks_event_failed_when_document_missing(self):
        IntegrationEvent.objects.create(
            direction=IntegrationDirection.OUTBOUND,
            source="wms.document_scan",
            target="antivirus",
            event_type="scan_document",
            payload={"model": "wms.AccountDocument", "pk": 99999},
            status=IntegrationStatus.PENDING,
        )

        result = process_document_scan_queue(limit=10)

        self.assertEqual(
            result,
            {"selected": 1, "processed": 0, "infected": 0, "failed": 1},
        )
        event = IntegrationEvent.objects.get()
        self.assertEqual(event.status, IntegrationStatus.FAILED)
        self.assertIn("Document introuvable", event.error_message)

    @mock.patch("wms.document_scan_queue.scan_uploaded_file")
    def test_process_document_scan_queue_marks_event_failed_on_scan_error(self, scan_mock):
        scan_mock.return_value = (DocumentScanStatus.ERROR, "scanner down")
        document = self._create_account_document()
        queue_document_scan(document)

        result = process_document_scan_queue(limit=10)

        self.assertEqual(
            result,
            {"selected": 1, "processed": 0, "infected": 0, "failed": 1},
        )
        event = IntegrationEvent.objects.get()
        self.assertEqual(event.status, IntegrationStatus.FAILED)
        self.assertEqual(event.error_message, "scanner down")

    @mock.patch("wms.document_scan_queue.scan_uploaded_file")
    def test_process_document_scan_queue_can_reprocess_failed_events(self, scan_mock):
        scan_mock.return_value = (DocumentScanStatus.CLEAN, "clean")
        document = self._create_account_document()
        queue_document_scan(document)
        event = IntegrationEvent.objects.get()
        event.status = IntegrationStatus.FAILED
        event.save(update_fields=["status"])

        result = process_document_scan_queue(limit=10, include_failed=True)

        self.assertEqual(result["selected"], 1)
        self.assertEqual(result["processed"], 1)
        event.refresh_from_db()
        self.assertEqual(event.status, IntegrationStatus.PROCESSED)

    @mock.patch("wms.document_scan_queue._claim_queue_event", return_value=0)
    def test_process_document_scan_queue_skips_when_claim_fails(self, _claim_mock):
        document = self._create_account_document()
        queue_document_scan(document)

        result = process_document_scan_queue(limit=10)

        self.assertEqual(
            result,
            {"selected": 0, "processed": 0, "infected": 0, "failed": 0},
        )

    def test_process_document_scan_queue_command_reports_summary(self):
        out = StringIO()
        call_command("process_document_scan_queue", "--limit=1", stdout=out)
        self.assertIn("Document scan queue processed:", out.getvalue())
