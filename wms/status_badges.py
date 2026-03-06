import re

BADGE_TONE_READY = "ready"
BADGE_TONE_PROGRESS = "progress"
BADGE_TONE_WARNING = "warning"
BADGE_TONE_ERROR = "error"

_DEFAULT_TONE = BADGE_TONE_PROGRESS

_DOMAIN_ALIASES = {
    "account_document": "document_review",
    "generated_print_artifact": "artifact",
    "integration_event": "integration",
    "order_document": "document_review",
    "public_account_request": "account_request",
    "shipment_tracking": "tracking",
    "tracking_event": "tracking",
}

_STATUS_TONES_BY_DOMAIN = {
    "shipment": {
        "draft": BADGE_TONE_PROGRESS,
        "picking": BADGE_TONE_PROGRESS,
        "packed": BADGE_TONE_READY,
        "planned": BADGE_TONE_PROGRESS,
        "shipped": BADGE_TONE_PROGRESS,
        "received_correspondent": BADGE_TONE_PROGRESS,
        "delivered": BADGE_TONE_READY,
    },
    "tracking": {
        "planning_ok": BADGE_TONE_PROGRESS,
        "planned": BADGE_TONE_PROGRESS,
        "moved_export": BADGE_TONE_PROGRESS,
        "boarding_ok": BADGE_TONE_PROGRESS,
        "received_correspondent": BADGE_TONE_PROGRESS,
        "received_recipient": BADGE_TONE_READY,
    },
    "carton": {
        "draft": BADGE_TONE_PROGRESS,
        "picking": BADGE_TONE_PROGRESS,
        "packed": BADGE_TONE_READY,
        "assigned": BADGE_TONE_PROGRESS,
        "labeled": BADGE_TONE_READY,
        "shipped": BADGE_TONE_READY,
    },
    "order": {
        "draft": BADGE_TONE_PROGRESS,
        "reserved": BADGE_TONE_PROGRESS,
        "preparing": BADGE_TONE_PROGRESS,
        "ready": BADGE_TONE_READY,
        "cancelled": BADGE_TONE_ERROR,
    },
    "order_review": {
        "pending_validation": BADGE_TONE_PROGRESS,
        "approved": BADGE_TONE_READY,
        "rejected": BADGE_TONE_ERROR,
        "changes_requested": BADGE_TONE_WARNING,
    },
    "document_review": {
        "pending": BADGE_TONE_PROGRESS,
        "approved": BADGE_TONE_READY,
        "rejected": BADGE_TONE_ERROR,
    },
    "account_request": {
        "pending": BADGE_TONE_PROGRESS,
        "approved": BADGE_TONE_READY,
        "rejected": BADGE_TONE_ERROR,
    },
    "receipt": {
        "draft": BADGE_TONE_PROGRESS,
        "received": BADGE_TONE_READY,
        "cancelled": BADGE_TONE_ERROR,
    },
    "product_lot": {
        "available": BADGE_TONE_READY,
        "quarantined": BADGE_TONE_WARNING,
        "hold": BADGE_TONE_WARNING,
        "expired": BADGE_TONE_ERROR,
    },
    "integration": {
        "pending": BADGE_TONE_PROGRESS,
        "processing": BADGE_TONE_PROGRESS,
        "processed": BADGE_TONE_READY,
        "failed": BADGE_TONE_ERROR,
    },
    "artifact": {
        "generated": BADGE_TONE_PROGRESS,
        "sync_pending": BADGE_TONE_PROGRESS,
        "synced": BADGE_TONE_READY,
        "sync_failed": BADGE_TONE_ERROR,
        "failed": BADGE_TONE_ERROR,
    },
}

_GLOBAL_STATUS_TONES = {
    "ok": BADGE_TONE_READY,
    "success": BADGE_TONE_READY,
    "completed": BADGE_TONE_READY,
    "done": BADGE_TONE_READY,
    "pending": BADGE_TONE_PROGRESS,
    "draft": BADGE_TONE_PROGRESS,
    "in_progress": BADGE_TONE_PROGRESS,
    "processing": BADGE_TONE_PROGRESS,
    "created": BADGE_TONE_PROGRESS,
    "planned": BADGE_TONE_PROGRESS,
    "warning": BADGE_TONE_WARNING,
    "alert": BADGE_TONE_WARNING,
    "hold": BADGE_TONE_WARNING,
    "error": BADGE_TONE_ERROR,
    "failed": BADGE_TONE_ERROR,
    "blocked": BADGE_TONE_ERROR,
    "rejected": BADGE_TONE_ERROR,
    "cancelled": BADGE_TONE_ERROR,
    "disputed": BADGE_TONE_ERROR,
}


def normalize_status_key(value):
    text = str(value or "").strip().lower()
    if not text:
        return ""
    text = re.sub(r"\s+", "_", text)
    text = text.replace("-", "_")
    return text


def resolve_status_tone(status_value, *, domain="", is_disputed=False):
    if is_disputed:
        return BADGE_TONE_ERROR

    status_key = normalize_status_key(status_value)
    if not status_key:
        return _DEFAULT_TONE

    domain_key = normalize_status_key(domain)
    domain_key = _DOMAIN_ALIASES.get(domain_key, domain_key)
    if domain_key:
        tone = _STATUS_TONES_BY_DOMAIN.get(domain_key, {}).get(status_key)
        if tone:
            return tone

    return _GLOBAL_STATUS_TONES.get(status_key, _DEFAULT_TONE)


def build_status_class(
    status_value, *, domain="", is_disputed=False, base_class="ui-comp-status-pill"
):
    tone = resolve_status_tone(
        status_value,
        domain=domain,
        is_disputed=is_disputed,
    )
    return f"{base_class} is-{tone}"
