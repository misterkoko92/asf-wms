from wms.document_scan_queue import process_document_scan_queue
from wms.jobs.runtime_tracking import record_job_run


def run_document_scan_queue_job(
    *,
    limit=100,
    include_failed=False,
    processing_timeout_seconds=None,
):
    return record_job_run(
        job_key="document_scan_queue",
        context_payload={
            "limit": limit,
            "include_failed": include_failed,
            "processing_timeout_seconds": processing_timeout_seconds,
        },
        runner=lambda: process_document_scan_queue(
            limit=limit,
            include_failed=include_failed,
            processing_timeout_seconds=processing_timeout_seconds,
        ),
    )
