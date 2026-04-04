from datetime import date
from unittest import mock

from django.test import TestCase

from wms.jobs.document_scan import run_document_scan_queue_job
from wms.jobs.email_queue import run_email_queue_job
from wms.jobs.pilotage import (
    run_capture_ops_pilotage_snapshot_job,
    run_evaluate_ops_escalations_job,
    run_refresh_ops_pilotage_job,
)
from wms.jobs.print_artifacts import run_print_artifact_queue_job
from wms.jobs.workflow_projection import run_rebuild_workflow_projection_job
from wms.models import OperationalJobRun


class OperationalJobRunTests(TestCase):
    @mock.patch(
        "wms.jobs.email_queue.process_email_queue",
        return_value={
            "selected": 1,
            "processed": 1,
            "failed": 0,
            "retried": 0,
            "deferred": 0,
        },
    )
    def test_run_email_queue_job_persists_successful_job_run(self, process_queue_mock):
        result = run_email_queue_job(limit=1, include_failed=True)

        self.assertEqual(result["processed"], 1)
        process_queue_mock.assert_called_once_with(
            limit=1,
            include_failed=True,
            max_attempts=None,
            retry_base_seconds=None,
            retry_max_seconds=None,
            processing_timeout_seconds=None,
        )
        run = OperationalJobRun.objects.get(job_key="email_queue")
        self.assertEqual(run.status, OperationalJobRun.Status.SUCCEEDED)
        self.assertEqual(run.trigger_source, "direct")
        self.assertEqual(run.context_payload["limit"], 1)
        self.assertEqual(run.context_payload["include_failed"], True)
        self.assertEqual(run.result_summary["processed"], 1)
        self.assertEqual(run.error_summary, {})
        self.assertIsNotNone(run.finished_at)

    @mock.patch(
        "wms.jobs.workflow_projection.rebuild_shipment_workflow_projections",
        return_value=3,
    )
    def test_run_workflow_projection_job_persists_scalar_summary(self, rebuild_mock):
        result = run_rebuild_workflow_projection_job()

        self.assertEqual(result, 3)
        rebuild_mock.assert_called_once_with()
        run = OperationalJobRun.objects.get(job_key="workflow_projection_rebuild")
        self.assertEqual(run.status, OperationalJobRun.Status.SUCCEEDED)
        self.assertEqual(run.result_summary, {"result": 3})

    @mock.patch("wms.jobs.pilotage._capture_ops_pilotage_snapshots", return_value=4)
    @mock.patch(
        "wms.jobs.pilotage._evaluate_ops_escalations",
        return_value={"open_count": 2, "resolved_count": 1},
    )
    def test_run_refresh_ops_pilotage_job_serializes_date_summary(
        self,
        evaluate_mock,
        capture_mock,
    ):
        result = run_refresh_ops_pilotage_job(snapshot_date=date(2026, 4, 2))

        self.assertEqual(result["snapshot_date"], date(2026, 4, 2))
        capture_mock.assert_called_once_with(snapshot_date=date(2026, 4, 2))
        evaluate_mock.assert_called_once_with(now=None)
        run = OperationalJobRun.objects.get(job_key="ops_pilotage_refresh")
        self.assertEqual(run.status, OperationalJobRun.Status.SUCCEEDED)
        self.assertEqual(run.result_summary["snapshot_date"], "2026-04-02")
        self.assertEqual(run.result_summary["captured_count"], 4)
        self.assertEqual(run.result_summary["open_count"], 2)

    @mock.patch("wms.jobs.pilotage.capture_ops_pilotage_snapshots", return_value=6)
    def test_run_capture_ops_pilotage_snapshot_job_persists_scalar_summary(self, capture_mock):
        result = run_capture_ops_pilotage_snapshot_job(snapshot_date=date(2026, 4, 3))

        self.assertEqual(result, 6)
        capture_mock.assert_called_once_with(snapshot_date=date(2026, 4, 3))
        run = OperationalJobRun.objects.get(job_key="ops_pilotage_snapshot_capture")
        self.assertEqual(run.status, OperationalJobRun.Status.SUCCEEDED)
        self.assertEqual(run.result_summary, {"result": 6})

    @mock.patch(
        "wms.jobs.pilotage.sync_ops_escalations",
        return_value={"open_count": 4, "resolved_count": 1},
    )
    def test_run_evaluate_ops_escalations_job_persists_summary(self, evaluate_mock):
        result = run_evaluate_ops_escalations_job(now="2026-04-03T10:00:00")

        self.assertEqual(result["open_count"], 4)
        evaluate_mock.assert_called_once_with(now="2026-04-03T10:00:00")
        run = OperationalJobRun.objects.get(job_key="ops_escalation_evaluation")
        self.assertEqual(run.status, OperationalJobRun.Status.SUCCEEDED)
        self.assertEqual(run.result_summary["open_count"], 4)

    @mock.patch(
        "wms.jobs.document_scan.process_document_scan_queue",
        return_value={"selected": 1, "processed": 1, "failed": 0},
    )
    def test_run_document_scan_queue_job_persists_summary(self, process_queue_mock):
        result = run_document_scan_queue_job(
            limit=4,
            include_failed=True,
            processing_timeout_seconds=120,
        )

        self.assertEqual(result["processed"], 1)
        process_queue_mock.assert_called_once_with(
            limit=4,
            include_failed=True,
            processing_timeout_seconds=120,
        )
        run = OperationalJobRun.objects.get(job_key="document_scan_queue")
        self.assertEqual(run.status, OperationalJobRun.Status.SUCCEEDED)
        self.assertEqual(run.context_payload["limit"], 4)
        self.assertEqual(run.result_summary["processed"], 1)

    @mock.patch(
        "wms.jobs.print_artifacts.process_print_artifact_queue",
        return_value={"selected": 2, "processed": 1, "failed": 1, "retried": 0},
    )
    def test_run_print_artifact_queue_job_persists_summary(self, process_queue_mock):
        result = run_print_artifact_queue_job(limit=3, include_failed=True, max_attempts=4)

        self.assertEqual(result["processed"], 1)
        process_queue_mock.assert_called_once_with(
            limit=3,
            include_failed=True,
            max_attempts=4,
        )
        run = OperationalJobRun.objects.get(job_key="print_artifact_queue")
        self.assertEqual(run.status, OperationalJobRun.Status.SUCCEEDED)
        self.assertEqual(run.context_payload["max_attempts"], 4)
        self.assertEqual(run.result_summary["failed"], 1)

    @mock.patch(
        "wms.jobs.print_artifacts.process_print_artifact_queue",
        return_value={
            "selected": 1,
            "processed": 0,
            "failed": 1,
            "retried": 0,
            "proof_sync": [
                {
                    "artifact_id": 42,
                    "file_name": "proof.pdf",
                    "relative_dir": "packs/B",
                    "onedrive_path": "packs/B/proof.pdf",
                    "result": "failed",
                    "error_message": "upload failed",
                }
            ],
        },
    )
    def test_run_print_artifact_queue_job_persists_proof_sync_preview(self, process_queue_mock):
        result = run_print_artifact_queue_job(limit=1)

        self.assertEqual(result["failed"], 1)
        process_queue_mock.assert_called_once_with(
            limit=1,
            include_failed=False,
            max_attempts=None,
        )
        run = OperationalJobRun.objects.get(job_key="print_artifact_queue")
        self.assertEqual(run.status, OperationalJobRun.Status.SUCCEEDED)
        self.assertNotIn("proof_sync", run.result_summary)
        self.assertEqual(run.result_summary["proof_sync_preview"][0]["artifact_id"], 42)
        self.assertEqual(run.result_summary["proof_sync_preview"][0]["result"], "failed")

    @mock.patch(
        "wms.jobs.email_queue.process_email_queue",
        side_effect=RuntimeError("boom"),
    )
    def test_run_email_queue_job_persists_failed_job_run(self, process_queue_mock):
        with self.assertRaisesMessage(RuntimeError, "boom"):
            run_email_queue_job(limit=1)

        process_queue_mock.assert_called_once()
        run = OperationalJobRun.objects.get(job_key="email_queue")
        self.assertEqual(run.status, OperationalJobRun.Status.FAILED)
        self.assertEqual(run.error_summary["type"], "RuntimeError")
        self.assertEqual(run.error_summary["message"], "boom")
        self.assertEqual(run.result_summary, {})
        self.assertIsNotNone(run.finished_at)
