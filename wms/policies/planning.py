from __future__ import annotations

from .pilotage import normalize_planning_thresholds

FLIGHT_LOAD_STATE_ORDER = {
    "overload": 0,
    "critical": 1,
    "tension": 2,
    "ok": 3,
    "unknown": 4,
}

FLIGHT_LOAD_STATE_LABELS = {
    "overload": "En surcharge",
    "critical": "Critique",
    "tension": "En tension",
    "ok": "OK",
    "unknown": "A renseigner",
}


def classify_planning_load_state(
    utilization_pct: int | None,
    *,
    tension_pct: int = 80,
    critical_pct: int = 95,
) -> str:
    if utilization_pct is None:
        return "unknown"
    resolved_tension, resolved_critical = normalize_planning_thresholds(
        tension_pct,
        critical_pct,
    )
    if utilization_pct > 100:
        return "overload"
    if utilization_pct >= resolved_critical:
        return "critical"
    if utilization_pct >= resolved_tension:
        return "tension"
    return "ok"
