from wms.jobs.runtime_tracking import record_job_run
from wms.print_pack_sync import process_print_artifact_queue


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
        runner=lambda: process_print_artifact_queue(
            limit=limit,
            include_failed=include_failed,
            max_attempts=max_attempts,
        ),
    )
