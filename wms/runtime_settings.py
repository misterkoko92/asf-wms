from dataclasses import dataclass

from django.conf import settings
from django.db.utils import OperationalError, ProgrammingError

from .models import WmsRuntimeSettings


def _safe_int(value, *, default, minimum):
    try:
        resolved = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, resolved)


@dataclass(frozen=True)
class RuntimeConfig:
    low_stock_threshold: int
    tracking_alert_hours: int
    workflow_blockage_hours: int
    stale_drafts_age_days: int
    email_queue_max_attempts: int
    email_queue_retry_base_seconds: int
    email_queue_retry_max_seconds: int
    email_queue_processing_timeout_seconds: int
    enable_shipment_track_legacy: bool


def _fallback_runtime_config() -> RuntimeConfig:
    retry_base_seconds = _safe_int(
        getattr(settings, "EMAIL_QUEUE_RETRY_BASE_SECONDS", 60),
        default=60,
        minimum=1,
    )
    retry_max_seconds = _safe_int(
        getattr(settings, "EMAIL_QUEUE_RETRY_MAX_SECONDS", 3600),
        default=3600,
        minimum=1,
    )
    return RuntimeConfig(
        low_stock_threshold=20,
        tracking_alert_hours=72,
        workflow_blockage_hours=72,
        stale_drafts_age_days=30,
        email_queue_max_attempts=_safe_int(
            getattr(settings, "EMAIL_QUEUE_MAX_ATTEMPTS", 5),
            default=5,
            minimum=1,
        ),
        email_queue_retry_base_seconds=retry_base_seconds,
        email_queue_retry_max_seconds=max(retry_base_seconds, retry_max_seconds),
        email_queue_processing_timeout_seconds=_safe_int(
            getattr(settings, "EMAIL_QUEUE_PROCESSING_TIMEOUT_SECONDS", 900),
            default=900,
            minimum=1,
        ),
        enable_shipment_track_legacy=bool(
            getattr(settings, "ENABLE_SHIPMENT_TRACK_LEGACY", True)
        ),
    )


def get_runtime_settings_instance():
    return WmsRuntimeSettings.get_solo()


def get_runtime_config() -> RuntimeConfig:
    fallback = _fallback_runtime_config()
    try:
        runtime = get_runtime_settings_instance()
    except (ProgrammingError, OperationalError):
        return fallback
    retry_base_seconds = _safe_int(
        runtime.email_queue_retry_base_seconds,
        default=fallback.email_queue_retry_base_seconds,
        minimum=1,
    )
    retry_max_seconds = _safe_int(
        runtime.email_queue_retry_max_seconds,
        default=fallback.email_queue_retry_max_seconds,
        minimum=1,
    )
    return RuntimeConfig(
        low_stock_threshold=_safe_int(
            runtime.low_stock_threshold,
            default=fallback.low_stock_threshold,
            minimum=1,
        ),
        tracking_alert_hours=_safe_int(
            runtime.tracking_alert_hours,
            default=fallback.tracking_alert_hours,
            minimum=1,
        ),
        workflow_blockage_hours=_safe_int(
            runtime.workflow_blockage_hours,
            default=fallback.workflow_blockage_hours,
            minimum=1,
        ),
        stale_drafts_age_days=_safe_int(
            runtime.stale_drafts_age_days,
            default=fallback.stale_drafts_age_days,
            minimum=1,
        ),
        email_queue_max_attempts=_safe_int(
            runtime.email_queue_max_attempts,
            default=fallback.email_queue_max_attempts,
            minimum=1,
        ),
        email_queue_retry_base_seconds=retry_base_seconds,
        email_queue_retry_max_seconds=max(retry_base_seconds, retry_max_seconds),
        email_queue_processing_timeout_seconds=_safe_int(
            runtime.email_queue_processing_timeout_seconds,
            default=fallback.email_queue_processing_timeout_seconds,
            minimum=1,
        ),
        enable_shipment_track_legacy=bool(runtime.enable_shipment_track_legacy),
    )


def is_shipment_track_legacy_enabled() -> bool:
    runtime_flag = get_runtime_config().enable_shipment_track_legacy
    env_flag = bool(getattr(settings, "ENABLE_SHIPMENT_TRACK_LEGACY", True))
    return env_flag and runtime_flag
