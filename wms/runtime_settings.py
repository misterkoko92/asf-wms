import os
from dataclasses import dataclass

from django.conf import settings
from django.db.utils import OperationalError, ProgrammingError

from .models import WmsRuntimeSettings
from .policies.pilotage import normalize_planning_thresholds


def _safe_int(value, *, default, minimum):
    try:
        resolved = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, resolved)


def _safe_float(value, *, default, minimum):
    try:
        resolved = float(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, resolved)


def _get_setting_or_env(name, *, default="", env_aliases=()):
    value = getattr(settings, name, None)
    if isinstance(value, str):
        value = value.strip()
    if value not in (None, ""):
        return value
    for env_name in (name, *env_aliases):
        env_value = os.environ.get(env_name)
        if env_value is None:
            continue
        env_value = env_value.strip()
        if env_value:
            return env_value
    return default


def _get_setting_or_env_int(name, *, default, minimum, env_aliases=()):
    value = getattr(settings, name, None)
    if value not in (None, ""):
        return _safe_int(value, default=default, minimum=minimum)
    for env_name in (name, *env_aliases):
        env_value = os.environ.get(env_name)
        if env_value in (None, ""):
            continue
        return _safe_int(env_value, default=default, minimum=minimum)
    return default


def _get_setting_or_env_float(name, *, default, minimum, env_aliases=()):
    value = getattr(settings, name, None)
    if value not in (None, ""):
        return _safe_float(value, default=default, minimum=minimum)
    for env_name in (name, *env_aliases):
        env_value = os.environ.get(env_name)
        if env_value in (None, ""):
            continue
        return _safe_float(env_value, default=default, minimum=minimum)
    return default


@dataclass(frozen=True)
class RuntimeConfig:
    low_stock_threshold: int
    tracking_alert_hours: int
    workflow_blockage_hours: int
    stale_drafts_age_days: int
    pilotage_dispute_unassigned_hours: int
    pilotage_workflow_blockage_unclaimed_hours: int
    pilotage_queue_backlog_threshold: int
    pilotage_planning_tension_pct: int
    pilotage_planning_critical_pct: int
    email_queue_max_attempts: int
    email_queue_retry_base_seconds: int
    email_queue_retry_max_seconds: int
    email_queue_processing_timeout_seconds: int
    enable_shipment_track_legacy: bool


@dataclass(frozen=True)
class PlanningFlightApiConfig:
    provider: str
    base_url: str
    api_key: str
    timeout_seconds: int
    max_calls_per_day: int
    min_delay_seconds: float
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
        pilotage_dispute_unassigned_hours=12,
        pilotage_workflow_blockage_unclaimed_hours=12,
        pilotage_queue_backlog_threshold=3,
        pilotage_planning_tension_pct=80,
        pilotage_planning_critical_pct=95,
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
    )


def get_runtime_settings_instance():
    return WmsRuntimeSettings.get_solo()


def get_runtime_config() -> RuntimeConfig:
    fallback = _fallback_runtime_config()
    try:
        runtime = get_runtime_settings_instance()
    except (ProgrammingError, OperationalError):
        return fallback
    planning_tension_pct, planning_critical_pct = normalize_planning_thresholds(
        runtime.pilotage_planning_tension_pct,
        runtime.pilotage_planning_critical_pct,
        default_tension=fallback.pilotage_planning_tension_pct,
        default_critical=fallback.pilotage_planning_critical_pct,
    )
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
        pilotage_dispute_unassigned_hours=_safe_int(
            runtime.pilotage_dispute_unassigned_hours,
            default=fallback.pilotage_dispute_unassigned_hours,
            minimum=1,
        ),
        pilotage_workflow_blockage_unclaimed_hours=_safe_int(
            runtime.pilotage_workflow_blockage_unclaimed_hours,
            default=fallback.pilotage_workflow_blockage_unclaimed_hours,
            minimum=1,
        ),
        pilotage_queue_backlog_threshold=_safe_int(
            runtime.pilotage_queue_backlog_threshold,
            default=fallback.pilotage_queue_backlog_threshold,
            minimum=1,
        ),
        pilotage_planning_tension_pct=_safe_int(
            planning_tension_pct,
            default=fallback.pilotage_planning_tension_pct,
            minimum=1,
        ),
        pilotage_planning_critical_pct=_safe_int(
            planning_critical_pct,
            default=fallback.pilotage_planning_critical_pct,
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


def get_planning_flight_api_config() -> PlanningFlightApiConfig:
    return PlanningFlightApiConfig(
        provider=str(
            _get_setting_or_env(
                "PLANNING_FLIGHT_API_PROVIDER",
                default="airfrance_klm",
            )
        )
        .strip()
        .lower(),
        base_url=str(_get_setting_or_env("PLANNING_FLIGHT_API_BASE_URL", default="")).strip(),
        api_key=str(
            _get_setting_or_env(
                "PLANNING_FLIGHT_API_KEY",
                default="",
                env_aliases=("AF_API_KEY",),
            )
        ).strip(),
        timeout_seconds=_get_setting_or_env_int(
            "PLANNING_FLIGHT_API_TIMEOUT_SECONDS",
            default=30,
            minimum=1,
        ),
        max_calls_per_day=_get_setting_or_env_int(
            "PLANNING_FLIGHT_API_MAX_CALLS_PER_DAY",
            default=100,
            minimum=1,
            env_aliases=("AF_MAX_CALLS_PER_DAY",),
        ),
        min_delay_seconds=_get_setting_or_env_float(
            "PLANNING_FLIGHT_API_MIN_DELAY_SECONDS",
            default=1.1,
            minimum=0.1,
            env_aliases=("AF_MIN_DELAY_SECONDS",),
        ),
        origin_iata=str(
            _get_setting_or_env(
                "PLANNING_FLIGHT_API_ORIGIN_IATA",
                default="CDG",
            )
        )
        .strip()
        .upper(),
        operating_airline_code=str(
            _get_setting_or_env(
                "PLANNING_FLIGHT_API_AIRLINE_CODE",
                default="AF",
            )
        )
        .strip()
        .upper(),
        time_origin_type=str(
            _get_setting_or_env(
                "PLANNING_FLIGHT_API_TIME_ORIGIN_TYPE",
                default="P",
                env_aliases=("AF_TIME_ORIGIN_TYPE",),
            )
        )
        .strip()
        .upper(),
    )
