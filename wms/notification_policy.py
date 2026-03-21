from __future__ import annotations


def _uniq_emails(values):
    emails = []
    seen = set()
    for raw in values:
        value = (raw or "").strip()
        if not value:
            continue
        lowered = value.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        emails.append(value)
    return emails


def resolve_reference_notification_emails(*references: dict | None) -> list[str]:
    emails = []
    for reference in references:
        if not isinstance(reference, dict):
            continue
        emails.extend(reference.get("notification_emails") or [])
    return _uniq_emails(emails)
