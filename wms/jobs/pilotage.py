from django.utils import timezone

from wms.jobs.runtime_tracking import record_job_run
from wms.ops_escalations import sync_ops_escalations
from wms.ops_pilotage_snapshots import capture_ops_pilotage_snapshots


def _capture_ops_pilotage_snapshots(*, snapshot_date):
    return capture_ops_pilotage_snapshots(snapshot_date=snapshot_date)


def _evaluate_ops_escalations(*, now=None):
    return sync_ops_escalations(now=now or timezone.now())


def run_capture_ops_pilotage_snapshot_job(*, snapshot_date):
    return record_job_run(
        job_key="ops_pilotage_snapshot_capture",
        context_payload={"snapshot_date": snapshot_date},
        runner=lambda: _capture_ops_pilotage_snapshots(snapshot_date=snapshot_date),
    )


def run_evaluate_ops_escalations_job(*, now=None):
    return record_job_run(
        job_key="ops_escalation_evaluation",
        context_payload={"now": now},
        runner=lambda: _evaluate_ops_escalations(now=now),
    )


def run_refresh_ops_pilotage_job(*, snapshot_date, now=None):
    return record_job_run(
        job_key="ops_pilotage_refresh",
        context_payload={"snapshot_date": snapshot_date, "now": now},
        runner=lambda: _run_refresh_ops_pilotage(snapshot_date=snapshot_date, now=now),
    )


def _run_refresh_ops_pilotage(*, snapshot_date, now=None):
    captured_count = _capture_ops_pilotage_snapshots(snapshot_date=snapshot_date)
    escalation_summary = _evaluate_ops_escalations(now=now)
    return {
        "snapshot_date": snapshot_date,
        "captured_count": captured_count,
        **escalation_summary,
    }
