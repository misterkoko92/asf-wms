from wms.jobs.runtime_tracking import record_job_run
from wms.print_pack_sync import process_print_artifact_queue


def _summarize_print_artifact_queue_result(result):
    summary = {
        "selected": result.get("selected", 0),
        "processed": result.get("processed", 0),
        "failed": result.get("failed", 0),
        "retried": result.get("retried", 0),
    }
    proof_sync = list(result.get("proof_sync", []))
    if proof_sync:
        summary["proof_sync_preview"] = proof_sync[:5]
    return summary


def run_print_artifact_queue_job(
    *,
    limit=20,
    include_failed=False,
    max_attempts=None,
):
    return record_job_run(
        job_key="print_artifact_queue",
        context_payload={
            "limit": limit,
            "include_failed": include_failed,
            "max_attempts": max_attempts,
        },
        result_summary_factory=_summarize_print_artifact_queue_result,
        runner=lambda: process_print_artifact_queue(
            limit=limit,
            include_failed=include_failed,
            max_attempts=max_attempts,
        ),
    )
