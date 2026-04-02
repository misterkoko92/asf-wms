from wms.emailing import process_email_queue
from wms.jobs.runtime_tracking import record_job_run


def run_email_queue_job(
    *,
    limit=100,
    include_failed=False,
    max_attempts=None,
    retry_base_seconds=None,
    retry_max_seconds=None,
    processing_timeout_seconds=None,
):
    return record_job_run(
        job_key="email_queue",
        context_payload={
            "limit": limit,
            "include_failed": include_failed,
            "max_attempts": max_attempts,
            "retry_base_seconds": retry_base_seconds,
            "retry_max_seconds": retry_max_seconds,
            "processing_timeout_seconds": processing_timeout_seconds,
        },
        runner=lambda: process_email_queue(
            limit=limit,
            include_failed=include_failed,
            max_attempts=max_attempts,
            retry_base_seconds=retry_base_seconds,
            retry_max_seconds=retry_max_seconds,
            processing_timeout_seconds=processing_timeout_seconds,
        ),
    )
