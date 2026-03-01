from io import StringIO
from unittest import mock

from django.core.files.base import ContentFile
from django.core.management import call_command
from django.test import TestCase, override_settings

from wms.models import GeneratedPrintArtifact, GeneratedPrintArtifactStatus
from wms.print_pack_sync import PrintArtifactSyncError, process_print_artifact_queue


class PrintPackSyncTests(TestCase):
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
