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
    org_roles_engine_enabled: bool
    org_roles_review_max_open_percent: int


@dataclass(frozen=True)
class PlanningFlightApiConfig:
    provider: str
    base_url: str
    api_key: str
    timeout_seconds: int
    origin_iata: str
    operating_airline_code: str
    time_origin_type: str


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
        enable_shipment_track_legacy=bool(getattr(settings, "ENABLE_SHIPMENT_TRACK_LEGACY", True)),
        org_roles_engine_enabled=bool(getattr(settings, "ORG_ROLES_ENGINE_ENABLED", False)),
        org_roles_review_max_open_percent=min(
            100,
            _safe_int(
                getattr(settings, "ORG_ROLES_REVIEW_MAX_OPEN_PERCENT", 20),
                default=20,
                minimum=0,
            ),
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
        org_roles_engine_enabled=bool(runtime.org_roles_engine_enabled),
        org_roles_review_max_open_percent=min(
            100,
            _safe_int(
                runtime.org_roles_review_max_open_percent,
                default=fallback.org_roles_review_max_open_percent,
                minimum=0,
            ),
        ),
    )


def is_shipment_track_legacy_enabled() -> bool:
    runtime_flag = get_runtime_config().enable_shipment_track_legacy
    env_flag = bool(getattr(settings, "ENABLE_SHIPMENT_TRACK_LEGACY", True))
    return env_flag and runtime_flag


def get_planning_flight_api_config() -> PlanningFlightApiConfig:
    return PlanningFlightApiConfig(
        provider=(getattr(settings, "PLANNING_FLIGHT_API_PROVIDER", "airfrance_klm") or "")
        .strip()
        .lower(),
        base_url=(getattr(settings, "PLANNING_FLIGHT_API_BASE_URL", "") or "").strip(),
        api_key=(getattr(settings, "PLANNING_FLIGHT_API_KEY", "") or "").strip(),
        timeout_seconds=_safe_int(
            getattr(settings, "PLANNING_FLIGHT_API_TIMEOUT_SECONDS", 30),
            default=30,
            minimum=1,
        ),
        origin_iata=(getattr(settings, "PLANNING_FLIGHT_API_ORIGIN_IATA", "CDG") or "CDG")
        .strip()
        .upper(),
        operating_airline_code=(getattr(settings, "PLANNING_FLIGHT_API_AIRLINE_CODE", "AF") or "AF")
        .strip()
        .upper(),
        time_origin_type=(getattr(settings, "PLANNING_FLIGHT_API_TIME_ORIGIN_TYPE", "P") or "P")
        .strip()
        .upper(),
    )
