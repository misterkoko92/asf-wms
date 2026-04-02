from __future__ import annotations

import shutil
from datetime import timedelta

from django.utils import timezone

from tools.planning_comm_helper import excel_runtime
from wms.document_scan_queue import (
    DOCUMENT_SCAN_BACKEND_CLAMAV,
    DOCUMENT_SCAN_BACKEND_NOOP,
    DOCUMENT_SCAN_QUEUE_EVENT_TYPE,
    DOCUMENT_SCAN_QUEUE_SOURCE,
    _clamav_command,
    _processing_timeout_seconds,
    _scan_backend,
)
from wms.models import IntegrationDirection, IntegrationEvent, IntegrationStatus


def _non_negative(value: int | None, *, option_name: str) -> int | None:
    if value is None:
        return None
    if value < 0:
        raise ValueError(f"{option_name} doit etre >= 0.")
    return value


def _scan_queue_queryset():
    return IntegrationEvent.objects.filter(
        direction=IntegrationDirection.OUTBOUND,
        source=DOCUMENT_SCAN_QUEUE_SOURCE,
        event_type=DOCUMENT_SCAN_QUEUE_EVENT_TYPE,
    )


def run_document_scan_runtime_check(
    *,
    allow_noop=False,
    max_pending=None,
    max_failed=0,
    max_stale_processing=0,
    processing_timeout_seconds=None,
):
    max_pending = _non_negative(max_pending, option_name="--max-pending")
    max_failed = _non_negative(max_failed, option_name="--max-failed")
    max_stale_processing = _non_negative(
        max_stale_processing,
        option_name="--max-stale-processing",
    )

    backend = _scan_backend()
    clamav_command = _clamav_command()
    clamav_available = bool(shutil.which(clamav_command))
    timeout_seconds = _processing_timeout_seconds(processing_timeout_seconds)

    queue_queryset = _scan_queue_queryset()
    counts = {
        IntegrationStatus.PENDING: queue_queryset.filter(status=IntegrationStatus.PENDING).count(),
        IntegrationStatus.PROCESSING: queue_queryset.filter(
            status=IntegrationStatus.PROCESSING
        ).count(),
        IntegrationStatus.FAILED: queue_queryset.filter(status=IntegrationStatus.FAILED).count(),
        IntegrationStatus.PROCESSED: queue_queryset.filter(
            status=IntegrationStatus.PROCESSED
        ).count(),
    }
    stale_cutoff = timezone.now() - timedelta(seconds=timeout_seconds)
    stale_processing = queue_queryset.filter(
        status=IntegrationStatus.PROCESSING,
        processed_at__lte=stale_cutoff,
    ).count()

    issues = []
    if backend == DOCUMENT_SCAN_BACKEND_NOOP and not allow_noop:
        issues.append(
            "DOCUMENT_SCAN_BACKEND=noop detecte sans --allow-noop (interdit en production)."
        )
    if backend == DOCUMENT_SCAN_BACKEND_CLAMAV and not clamav_available:
        issues.append(f"Commande ClamAV introuvable: '{clamav_command}'.")
    if max_pending is not None and counts[IntegrationStatus.PENDING] > max_pending:
        issues.append(
            f"pending={counts[IntegrationStatus.PENDING]} depasse --max-pending={max_pending}."
        )
    if max_failed is not None and counts[IntegrationStatus.FAILED] > max_failed:
        issues.append(
            f"failed={counts[IntegrationStatus.FAILED]} depasse --max-failed={max_failed}."
        )
    if max_stale_processing is not None and stale_processing > max_stale_processing:
        issues.append(
            "stale_processing="
            f"{stale_processing} depasse --max-stale-processing={max_stale_processing}."
        )

    return {
        "backend": backend,
        "clamav_command": clamav_command,
        "clamav_available": clamav_available,
        "counts": counts,
        "stale_processing": stale_processing,
        "timeout_seconds": timeout_seconds,
        "issues": issues,
    }


def get_planning_pdf_runtime_status():
    return excel_runtime.get_excel_runtime_status()


def build_planning_pdf_runtime_unavailable_message(runtime_status):
    return excel_runtime.build_runtime_unavailable_message(runtime_status)
