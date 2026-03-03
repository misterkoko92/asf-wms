from io import BytesIO, StringIO
from types import SimpleNamespace
from unittest import mock
from urllib import error as urllib_error

from django.core.files.base import ContentFile
from django.core.management import call_command
from django.test import TestCase, override_settings

from wms.models import GeneratedPrintArtifact, GeneratedPrintArtifactStatus
from wms.print_pack_sync import (
    PrintArtifactSyncError,
    _artifact_filename,
    _artifact_onedrive_path,
    _artifact_relative_dir,
    _upload_artifact_pdf_to_onedrive,
    _validate_https_url,
    process_print_artifact_queue,
)


class PrintPackSyncTests(TestCase):
    def _create_artifact(self, *, filename="artifact.pdf", payload=b"%PDF-1", pack_code="B"):
        artifact = GeneratedPrintArtifact.objects.create(
            pack_code=pack_code,
            status=GeneratedPrintArtifactStatus.SYNC_PENDING,
        )
        artifact.pdf_file.save(filename, ContentFile(payload), save=True)
        return artifact

    @override_settings(GRAPH_REQUEST_TIMEOUT_SECONDS=12)
    def test_process_print_artifact_queue_marks_artifact_synced_on_success(self):
        artifact = GeneratedPrintArtifact.objects.create(
            pack_code="B",
            status=GeneratedPrintArtifactStatus.SYNC_PENDING,
        )
        artifact.pdf_file.save("artifact.pdf", ContentFile(b"%PDF-1"), save=True)

        with mock.patch(
            "wms.print_pack_sync._upload_artifact_pdf_to_onedrive",
            return_value="prints/shipments/SHP-001/artifact.pdf",
        ) as upload_mock:
            result = process_print_artifact_queue(limit=5)

        artifact.refresh_from_db()
        self.assertEqual(
            result,
            {"selected": 1, "processed": 1, "failed": 0, "retried": 0},
        )
        self.assertEqual(artifact.status, GeneratedPrintArtifactStatus.SYNCED)
        self.assertEqual(artifact.sync_attempts, 1)
        self.assertEqual(artifact.onedrive_path, "prints/shipments/SHP-001/artifact.pdf")
        self.assertEqual(artifact.last_sync_error, "")
        upload_mock.assert_called_once_with(artifact=artifact, timeout=12)

    def test_process_print_artifact_queue_tracks_retry_and_failure(self):
        retry_artifact = GeneratedPrintArtifact.objects.create(
            pack_code="B",
            status=GeneratedPrintArtifactStatus.SYNC_PENDING,
            sync_attempts=0,
        )
        retry_artifact.pdf_file.save("retry.pdf", ContentFile(b"%PDF-1"), save=True)

        fail_artifact = GeneratedPrintArtifact.objects.create(
            pack_code="C",
            status=GeneratedPrintArtifactStatus.SYNC_PENDING,
            sync_attempts=1,
        )
        fail_artifact.pdf_file.save("fail.pdf", ContentFile(b"%PDF-2"), save=True)

        with mock.patch(
            "wms.print_pack_sync._upload_artifact_pdf_to_onedrive",
            side_effect=PrintArtifactSyncError("upload failed"),
        ):
            result = process_print_artifact_queue(limit=5, max_attempts=2)

        retry_artifact.refresh_from_db()
        fail_artifact.refresh_from_db()
        self.assertEqual(
            result,
            {"selected": 2, "processed": 0, "failed": 1, "retried": 1},
        )
        self.assertEqual(retry_artifact.status, GeneratedPrintArtifactStatus.SYNC_PENDING)
        self.assertEqual(retry_artifact.sync_attempts, 1)
        self.assertIn("upload failed", retry_artifact.last_sync_error)
        self.assertEqual(fail_artifact.status, GeneratedPrintArtifactStatus.SYNC_FAILED)
        self.assertEqual(fail_artifact.sync_attempts, 2)
        self.assertIn("upload failed", fail_artifact.last_sync_error)

    def test_process_print_artifact_queue_only_retries_failed_when_flag_enabled(self):
        artifact = GeneratedPrintArtifact.objects.create(
            pack_code="D",
            status=GeneratedPrintArtifactStatus.SYNC_FAILED,
            sync_attempts=1,
        )
        artifact.pdf_file.save("failed.pdf", ContentFile(b"%PDF-3"), save=True)

        with mock.patch(
            "wms.print_pack_sync._upload_artifact_pdf_to_onedrive",
            return_value="prints/failed.pdf",
        ) as upload_mock:
            result = process_print_artifact_queue(limit=5)
            result_retry = process_print_artifact_queue(limit=5, include_failed=True)

        artifact.refresh_from_db()
        self.assertEqual(result, {"selected": 0, "processed": 0, "failed": 0, "retried": 0})
        self.assertEqual(
            result_retry,
            {"selected": 1, "processed": 1, "failed": 0, "retried": 0},
        )
        self.assertEqual(artifact.status, GeneratedPrintArtifactStatus.SYNCED)
        upload_mock.assert_called_once()

    def test_management_command_delegates_to_processor(self):
        stdout = StringIO()
        with mock.patch(
            "wms.management.commands.process_print_artifact_queue.process_print_artifact_queue",
            return_value={"selected": 2, "processed": 1, "failed": 0, "retried": 1},
        ) as process_mock:
            call_command(
                "process_print_artifact_queue",
                "--limit",
                "10",
                "--include-failed",
                stdout=stdout,
            )

        process_mock.assert_called_once_with(
            limit=10,
            include_failed=True,
            max_attempts=None,
        )
        self.assertIn("processed=1", stdout.getvalue())

    def test_validate_https_url_rejects_non_https(self):
        with self.assertRaisesMessage(
            PrintArtifactSyncError,
            "OneDrive endpoint must use HTTPS.",
        ):
            _validate_https_url("http://graph.microsoft.com/v1.0/me/drive")

    def test_artifact_filename_and_relative_path_helpers(self):
        unnamed = SimpleNamespace(
            id=7,
            pack_code="B",
            pdf_file=SimpleNamespace(name="  "),
        )
        self.assertEqual(_artifact_filename(unnamed), "print-pack-B-7.pdf")

        named_without_extension = SimpleNamespace(
            id=8,
            pack_code="C",
            pdf_file=SimpleNamespace(name="generated/label"),
        )
        self.assertEqual(_artifact_filename(named_without_extension), "label.pdf")

        named_with_extension = SimpleNamespace(
            id=9,
            pack_code="D",
            pdf_file=SimpleNamespace(name="generated/already.pdf"),
        )
        self.assertEqual(_artifact_filename(named_with_extension), "already.pdf")

    @override_settings(GRAPH_WORK_DIR="/exports/")
    def test_artifact_relative_dir_and_onedrive_path_helpers(self):
        by_shipment = SimpleNamespace(
            id=1,
            pack_code="B",
            shipment=SimpleNamespace(reference="SHP-001"),
            carton=None,
            pdf_file=SimpleNamespace(name="labels/a.pdf"),
        )
        self.assertEqual(_artifact_relative_dir(by_shipment), "exports/shipments/SHP-001")
        self.assertEqual(_artifact_onedrive_path(by_shipment), "exports/shipments/SHP-001/a.pdf")

        by_carton = SimpleNamespace(
            id=2,
            pack_code="B",
            shipment=None,
            carton=SimpleNamespace(code="CT-10"),
            pdf_file=SimpleNamespace(name="labels/b.pdf"),
        )
        self.assertEqual(_artifact_relative_dir(by_carton), "exports/cartons/CT-10")
        self.assertEqual(_artifact_onedrive_path(by_carton), "exports/cartons/CT-10/b.pdf")

        by_pack_code = SimpleNamespace(
            id=3,
            pack_code="",
            shipment=None,
            carton=None,
            pdf_file=SimpleNamespace(name="labels/c.pdf"),
        )
        self.assertEqual(_artifact_relative_dir(by_pack_code), "exports/packs/unknown")
        self.assertEqual(_artifact_onedrive_path(by_pack_code), "exports/packs/unknown/c.pdf")

    @override_settings(GRAPH_DRIVE_ID="drive-123")
    def test_upload_artifact_pdf_to_onedrive_success_returns_path(self):
        artifact = self._create_artifact(filename="uploads/final-label.pdf", pack_code="L")

        response = mock.Mock()
        response.read.return_value = b""
        response.status = 201
        cm = mock.MagicMock()
        cm.__enter__.return_value = response
        cm.__exit__.return_value = False

        with mock.patch(
            "wms.print_pack_sync.get_client_credentials_token",
            return_value="token-abc",
        ) as token_mock, mock.patch(
            "wms.print_pack_sync.request.urlopen",
            return_value=cm,
        ) as urlopen_mock:
            onedrive_path = _upload_artifact_pdf_to_onedrive(artifact=artifact, timeout=9)

        generated_filename = artifact.pdf_file.name.split("/")[-1]
        self.assertEqual(onedrive_path, f"packs/L/{generated_filename}")
        token_mock.assert_called_once_with(timeout=9)
        req = urlopen_mock.call_args.args[0]
        self.assertEqual(req.get_method(), "PUT")
        self.assertIn(
            f"/drives/drive-123/root:/packs/L/{generated_filename}:/content",
            req.full_url,
        )
        self.assertEqual(urlopen_mock.call_args.kwargs["timeout"], 9)

    @override_settings(GRAPH_DRIVE_ID="")
    def test_upload_artifact_pdf_to_onedrive_fails_without_drive_id(self):
        artifact = self._create_artifact()
        with self.assertRaisesMessage(
            PrintArtifactSyncError,
            "Missing GRAPH_DRIVE_ID for OneDrive upload.",
        ):
            _upload_artifact_pdf_to_onedrive(artifact=artifact, timeout=3)

    @override_settings(GRAPH_DRIVE_ID="drive-123")
    def test_upload_artifact_pdf_to_onedrive_fails_without_pdf(self):
        artifact = GeneratedPrintArtifact.objects.create(
            pack_code="X",
            status=GeneratedPrintArtifactStatus.SYNC_PENDING,
        )
        with self.assertRaisesMessage(
            PrintArtifactSyncError,
            "Artifact has no PDF file to upload.",
        ):
            _upload_artifact_pdf_to_onedrive(artifact=artifact, timeout=3)

    @override_settings(GRAPH_DRIVE_ID="drive-123")
    def test_upload_artifact_pdf_to_onedrive_fails_when_payload_is_empty(self):
        artifact = self._create_artifact(payload=b"")
        with mock.patch(
            "wms.print_pack_sync.get_client_credentials_token",
            return_value="token-abc",
        ):
            with self.assertRaisesMessage(
                PrintArtifactSyncError,
                "Artifact PDF payload is empty.",
            ):
                _upload_artifact_pdf_to_onedrive(artifact=artifact, timeout=3)

    @override_settings(GRAPH_DRIVE_ID="drive-123")
    def test_upload_artifact_pdf_to_onedrive_wraps_http_errors(self):
        artifact = self._create_artifact()
        http_error = urllib_error.HTTPError(
            url="https://graph.microsoft.com",
            code=429,
            msg="Too Many Requests",
            hdrs=None,
            fp=BytesIO(b'{"error":"throttled"}'),
        )
        with mock.patch(
            "wms.print_pack_sync.get_client_credentials_token",
            return_value="token-abc",
        ), mock.patch(
            "wms.print_pack_sync.request.urlopen",
            side_effect=http_error,
        ):
            with self.assertRaisesMessage(
                PrintArtifactSyncError,
                "OneDrive upload failed with HTTP 429",
            ):
                _upload_artifact_pdf_to_onedrive(artifact=artifact, timeout=3)

    @override_settings(GRAPH_DRIVE_ID="drive-123")
    def test_upload_artifact_pdf_to_onedrive_wraps_url_errors(self):
        artifact = self._create_artifact()
        with mock.patch(
            "wms.print_pack_sync.get_client_credentials_token",
            return_value="token-abc",
        ), mock.patch(
            "wms.print_pack_sync.request.urlopen",
            side_effect=urllib_error.URLError("connection reset"),
        ):
            with self.assertRaisesMessage(
                PrintArtifactSyncError,
                "OneDrive upload failed:",
            ):
                _upload_artifact_pdf_to_onedrive(artifact=artifact, timeout=3)
