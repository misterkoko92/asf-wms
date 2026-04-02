from datetime import date
from unittest import mock

from django.test import TestCase

from wms.jobs.email_queue import run_email_queue_job
from wms.jobs.pilotage import run_refresh_ops_pilotage_job
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
