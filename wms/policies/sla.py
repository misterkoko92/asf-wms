from __future__ import annotations


def classify_sla_delay(delay_hours: float, *, threshold_hours: int) -> str:
    return "persistent" if delay_hours > threshold_hours else "new"


def build_sla_alert_classification(delay_hours: float, *, threshold_hours: int) -> dict[str, str]:
    freshness = classify_sla_delay(delay_hours, threshold_hours=threshold_hours)
    if delay_hours > threshold_hours * 2:
        severity = "critical"
        priority = "high"
    elif freshness == "persistent":
        severity = "high"
        priority = "high"
    else:
        severity = "high"
        priority = "medium"
    return {
        "freshness": freshness,
        "severity": severity,
        "priority": priority,
    }
