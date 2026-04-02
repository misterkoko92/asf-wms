from __future__ import annotations

import json
from collections.abc import Callable
from typing import TypeVar

from django.core.serializers.json import DjangoJSONEncoder
from django.utils import timezone

from wms.models_domain.integration import OperationalJobRun

T = TypeVar("T")


def _normalize_summary(value):
    if value is None:
        payload = {}
    elif isinstance(value, dict):
        payload = value
    else:
        payload = {"result": value}
    return json.loads(json.dumps(payload, cls=DjangoJSONEncoder))


def record_job_run(
    *,
    job_key: str,
    runner: Callable[[], T],
    trigger_source: str = "direct",
    context_payload: dict | None = None,
) -> T:
    run = OperationalJobRun.objects.create(
        job_key=job_key,
        trigger_source=trigger_source,
        status=OperationalJobRun.Status.RUNNING,
        context_payload=_normalize_summary(context_payload or {}),
    )

    try:
        result = runner()
    except Exception as exc:
        run.status = OperationalJobRun.Status.FAILED
        run.finished_at = timezone.now()
        run.error_summary = _normalize_summary(
            {
                "type": exc.__class__.__name__,
                "message": str(exc),
            }
        )
        run.save(update_fields=["status", "finished_at", "error_summary"])
        raise

    run.status = OperationalJobRun.Status.SUCCEEDED
    run.finished_at = timezone.now()
    run.result_summary = _normalize_summary(result)
    run.save(update_fields=["status", "finished_at", "result_summary"])
    return result
