from __future__ import annotations


def normalize_planning_thresholds(
    tension_pct: object,
    critical_pct: object,
    *,
    default_tension: int = 80,
    default_critical: int = 95,
    minimum: int = 1,
) -> tuple[int, int]:
    resolved_tension = _coerce_int(
        tension_pct,
        minimum=minimum,
        fallback=default_tension,
    )
    resolved_critical = _coerce_int(
        critical_pct,
        minimum=minimum,
        fallback=default_critical,
    )
    return resolved_tension, max(resolved_tension, resolved_critical)


def _coerce_int(value: object, *, minimum: int, fallback: int) -> int:
    try:
        resolved = int(value)
    except (TypeError, ValueError):
        return fallback
    return max(minimum, resolved)
