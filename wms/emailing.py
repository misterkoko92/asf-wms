import json
import logging
import os
from datetime import timedelta
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.db.models import Q
from django.utils.dateparse import parse_datetime
from django.utils import timezone

from .models import (
    IntegrationDirection,
    IntegrationEvent,
    IntegrationStatus,
)
from .runtime_settings import get_runtime_config

LOGGER = logging.getLogger(__name__)
BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"
BREVO_API_EXPECTED_HOST = "api.brevo.com"
BREVO_API_EXPECTED_PATH = "/v3/smtp/email"
EMAIL_QUEUE_SOURCE = "wms.email"
EMAIL_QUEUE_TARGET = "smtp"
EMAIL_QUEUE_EVENT_TYPE = "send_email"
EMAIL_QUEUE_META_KEY = "_queue"
EMAIL_QUEUE_DEFAULT_MAX_ATTEMPTS = 5
EMAIL_QUEUE_DEFAULT_RETRY_BASE_SECONDS = 60
EMAIL_QUEUE_DEFAULT_RETRY_MAX_SECONDS = 3600
EMAIL_QUEUE_DEFAULT_PROCESSING_TIMEOUT_SECONDS = 900

EMAIL_PAYLOAD_SUBJECT_KEY = "subject"
EMAIL_PAYLOAD_MESSAGE_KEY = "message"
EMAIL_PAYLOAD_RECIPIENT_KEY = "recipient"
EMAIL_PAYLOAD_HTML_MESSAGE_KEY = "html_message"
EMAIL_PAYLOAD_TAGS_KEY = "tags"

PROCESS_RESULT_SELECTED = "selected"
PROCESS_RESULT_PROCESSED = "processed"
PROCESS_RESULT_FAILED = "failed"
PROCESS_RESULT_RETRIED = "retried"
PROCESS_RESULT_DEFERRED = "deferred"


def get_admin_emails():
    User = get_user_model()
    return list(
        User.objects.filter(is_superuser=True, is_active=True)
        .exclude(email="")
        .values_list("email", flat=True)
    )


def _normalize_recipients(recipient):
    recipients = recipient
    if isinstance(recipients, str):
        recipients = [recipients]
    if recipients is None:
        return []
    return [item for item in recipients if item]


def _safe_int(value, *, default, minimum):
    try:
        int_value = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, int_value)


def _email_queue_config(
    *,
    max_attempts=None,
    retry_base_seconds=None,
    retry_max_seconds=None,
    processing_timeout_seconds=None,
):
    runtime_config = get_runtime_config()
    settings_max_attempts = runtime_config.email_queue_max_attempts
    settings_retry_base = runtime_config.email_queue_retry_base_seconds
    settings_retry_max = runtime_config.email_queue_retry_max_seconds
    settings_processing_timeout = runtime_config.email_queue_processing_timeout_seconds

    resolved_max_attempts = _safe_int(
        settings_max_attempts if max_attempts is None else max_attempts,
        default=EMAIL_QUEUE_DEFAULT_MAX_ATTEMPTS,
        minimum=1,
    )
    resolved_retry_base = _safe_int(
        settings_retry_base if retry_base_seconds is None else retry_base_seconds,
        default=EMAIL_QUEUE_DEFAULT_RETRY_BASE_SECONDS,
        minimum=1,
    )
    resolved_retry_max = _safe_int(
        settings_retry_max if retry_max_seconds is None else retry_max_seconds,
        default=EMAIL_QUEUE_DEFAULT_RETRY_MAX_SECONDS,
        minimum=1,
    )
    resolved_processing_timeout = _safe_int(
        (
            settings_processing_timeout
            if processing_timeout_seconds is None
            else processing_timeout_seconds
        ),
        default=EMAIL_QUEUE_DEFAULT_PROCESSING_TIMEOUT_SECONDS,
        minimum=1,
    )
    resolved_retry_max = max(resolved_retry_max, resolved_retry_base)

    return {
        "max_attempts": resolved_max_attempts,
        "retry_base_seconds": resolved_retry_base,
        "retry_max_seconds": resolved_retry_max,
        "processing_timeout_seconds": resolved_processing_timeout,
    }


def _parse_next_attempt(value):
    if not value:
        return None
    parsed = parse_datetime(str(value))
    if parsed is None:
        return None
    if timezone.is_naive(parsed):
        return timezone.make_aware(parsed, timezone.get_current_timezone())
    return parsed


def _queue_meta(payload):
    raw_meta = payload.get(EMAIL_QUEUE_META_KEY)
    if not isinstance(raw_meta, dict):
        return {"attempts": 0, "next_attempt_at": None}
    attempts = _safe_int(raw_meta.get("attempts"), default=0, minimum=0)
    next_attempt_at = _parse_next_attempt(raw_meta.get("next_attempt_at"))
    return {"attempts": attempts, "next_attempt_at": next_attempt_at}


def _set_queue_meta(payload, *, attempts, next_attempt_at):
    payload[EMAIL_QUEUE_META_KEY] = {
        "attempts": _safe_int(attempts, default=0, minimum=0),
        "next_attempt_at": next_attempt_at.isoformat() if next_attempt_at else None,
    }


def _compute_retry_delay_seconds(*, attempts, retry_base_seconds, retry_max_seconds):
    power = max(0, attempts - 1)
    delay = retry_base_seconds * (2**power)
    return min(retry_max_seconds, delay)


def _base_email_queue_queryset():
    return IntegrationEvent.objects.filter(
        direction=IntegrationDirection.OUTBOUND,
        source=EMAIL_QUEUE_SOURCE,
        event_type=EMAIL_QUEUE_EVENT_TYPE,
    )


def _coerce_process_limit(limit):
    return _safe_int(limit, default=100, minimum=1)


def _queue_candidate_statuses(include_failed):
    statuses = [IntegrationStatus.PENDING]
    if include_failed:
        statuses.append(IntegrationStatus.FAILED)
    return statuses


def _queue_claim_filter(*, statuses, stale_processing_before):
    return Q(status__in=statuses) | Q(
        status=IntegrationStatus.PROCESSING,
        processed_at__lte=stale_processing_before,
    )


def _selector_queryset(queue_queryset, *, statuses, stale_processing_before):
    return queue_queryset.filter(
        _queue_claim_filter(
            statuses=statuses,
            stale_processing_before=stale_processing_before,
        )
    ).order_by("created_at", "id")


def _should_defer_event(event, *, now):
    payload = event.payload or {}
    meta = _queue_meta(payload)
    return (
        event.status == IntegrationStatus.PENDING
        and meta["next_attempt_at"]
        and meta["next_attempt_at"] > now
    )


def _claim_queue_event(
    queue_queryset,
    *,
    event,
    statuses,
    stale_processing_before,
):
    return queue_queryset.filter(pk=event.pk).filter(
        _queue_claim_filter(
            statuses=statuses,
            stale_processing_before=stale_processing_before,
        )
    ).update(
        status=IntegrationStatus.PROCESSING,
        processed_at=timezone.now(),
        error_message="",
    )


def _send_event_payload(payload):
    return send_email_safe(
        subject=payload.get(EMAIL_PAYLOAD_SUBJECT_KEY) or "",
        message=payload.get(EMAIL_PAYLOAD_MESSAGE_KEY) or "",
        recipient=payload.get(EMAIL_PAYLOAD_RECIPIENT_KEY) or [],
        html_message=payload.get(EMAIL_PAYLOAD_HTML_MESSAGE_KEY) or None,
        tags=payload.get(EMAIL_PAYLOAD_TAGS_KEY) or None,
    )


def _apply_send_result(*, event, payload, meta, queue_config):
    event.processed_at = timezone.now()

    if _send_event_payload(payload):
        event.status = IntegrationStatus.PROCESSED
        event.error_message = ""
        _set_queue_meta(
            payload,
            attempts=meta["attempts"],
            next_attempt_at=None,
        )
        return PROCESS_RESULT_PROCESSED

    attempts = meta["attempts"] + 1
    if attempts >= queue_config["max_attempts"]:
        event.status = IntegrationStatus.FAILED
        event.error_message = (
            "send_email_safe returned False "
            f"after {attempts} attempt(s)."
        )
        _set_queue_meta(
            payload,
            attempts=attempts,
            next_attempt_at=None,
        )
        return PROCESS_RESULT_FAILED

    retry_delay = _compute_retry_delay_seconds(
        attempts=attempts,
        retry_base_seconds=queue_config["retry_base_seconds"],
        retry_max_seconds=queue_config["retry_max_seconds"],
    )
    next_attempt_at = timezone.now() + timedelta(seconds=retry_delay)
    event.status = IntegrationStatus.PENDING
    event.error_message = (
        "send_email_safe returned False "
        f"(retry {attempts}/{queue_config['max_attempts']} "
        f"in {retry_delay}s)."
    )
    _set_queue_meta(
        payload,
        attempts=attempts,
        next_attempt_at=next_attempt_at,
    )
    return PROCESS_RESULT_RETRIED


def _build_enqueue_payload(
    *,
    subject,
    message,
    recipients,
    html_message=None,
    tags=None,
):
    payload = {
        EMAIL_PAYLOAD_SUBJECT_KEY: subject,
        EMAIL_PAYLOAD_MESSAGE_KEY: message,
        EMAIL_PAYLOAD_RECIPIENT_KEY: recipients,
    }
    if html_message:
        payload[EMAIL_PAYLOAD_HTML_MESSAGE_KEY] = html_message
    if tags:
        payload[EMAIL_PAYLOAD_TAGS_KEY] = list(tags)
    return payload


def _brevo_settings():
    api_key = getattr(settings, "BREVO_API_KEY", "") or os.environ.get("BREVO_API_KEY", "")
    sender_email = (
        getattr(settings, "BREVO_SENDER_EMAIL", "")
        or os.environ.get("BREVO_SENDER_EMAIL", "")
        or settings.DEFAULT_FROM_EMAIL
    )
    sender_name = getattr(settings, "BREVO_SENDER_NAME", "") or os.environ.get(
        "BREVO_SENDER_NAME", ""
    )
    reply_to = getattr(settings, "BREVO_REPLY_TO_EMAIL", "") or os.environ.get(
        "BREVO_REPLY_TO_EMAIL", ""
    )
    return api_key, sender_email, sender_name, reply_to


def _send_with_brevo(*, subject, message, recipients, html_message=None, tags=None):
    api_key, sender_email, sender_name, reply_to = _brevo_settings()
    if not api_key or not sender_email:
        return False
    payload = {
        "sender": {"email": sender_email, "name": sender_name or sender_email},
        "to": [{"email": email} for email in recipients],
        "subject": subject,
        "textContent": message,
    }
    if html_message:
        payload["htmlContent"] = html_message
    if reply_to:
        payload["replyTo"] = {"email": reply_to}
    if tags:
        payload["tags"] = list(tags)
    try:
        parsed_url = urlparse(BREVO_API_URL)
        if (
            parsed_url.scheme != "https"
            or parsed_url.netloc != BREVO_API_EXPECTED_HOST
            or parsed_url.path != BREVO_API_EXPECTED_PATH
        ):
            raise ValueError("Invalid Brevo API URL configuration")
        request = Request(
            BREVO_API_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={"api-key": api_key, "Content-Type": "application/json"},
        )
        with urlopen(request, timeout=10) as response:  # nosec B310
            response.read()
        return True
    except (HTTPError, URLError, ValueError) as exc:
        LOGGER.warning("Brevo email failed: %s", exc)
    return False


def send_email_safe(*, subject, message, recipient, html_message=None, tags=None):
    recipients = _normalize_recipients(recipient)
    if not recipients:
        return False
    if _send_with_brevo(
        subject=subject,
        message=message,
        recipients=recipients,
        html_message=html_message,
        tags=tags,
    ):
        return True
    try:
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            recipients,
            fail_silently=False,
            html_message=html_message,
        )
    except Exception as exc:  # pragma: no cover - defensive logging
        LOGGER.warning("Django send_mail failed: %s", exc)
        return False
    return True


def enqueue_email_safe(*, subject, message, recipient, html_message=None, tags=None):
    recipients = _normalize_recipients(recipient)
    if not recipients:
        return False
    payload = _build_enqueue_payload(
        subject=subject,
        message=message,
        recipients=recipients,
        html_message=html_message,
        tags=tags,
    )
    _set_queue_meta(payload, attempts=0, next_attempt_at=None)
    IntegrationEvent.objects.create(
        direction=IntegrationDirection.OUTBOUND,
        source=EMAIL_QUEUE_SOURCE,
        target=EMAIL_QUEUE_TARGET,
        event_type=EMAIL_QUEUE_EVENT_TYPE,
        payload=payload,
        status=IntegrationStatus.PENDING,
    )
    return True


def process_email_queue(
    *,
    limit=100,
    include_failed=False,
    max_attempts=None,
    retry_base_seconds=None,
    retry_max_seconds=None,
    processing_timeout_seconds=None,
):
    safe_limit = _coerce_process_limit(limit)
    queue_config = _email_queue_config(
        max_attempts=max_attempts,
        retry_base_seconds=retry_base_seconds,
        retry_max_seconds=retry_max_seconds,
        processing_timeout_seconds=processing_timeout_seconds,
    )
    now = timezone.now()
    stale_processing_before = now - timedelta(
        seconds=queue_config["processing_timeout_seconds"]
    )

    statuses = _queue_candidate_statuses(include_failed)

    queue_queryset = _base_email_queue_queryset()
    selector_queryset = _selector_queryset(
        queue_queryset,
        statuses=statuses,
        stale_processing_before=stale_processing_before,
    )

    selected_events = []
    result = {
        PROCESS_RESULT_SELECTED: 0,
        PROCESS_RESULT_PROCESSED: 0,
        PROCESS_RESULT_FAILED: 0,
        PROCESS_RESULT_RETRIED: 0,
        PROCESS_RESULT_DEFERRED: 0,
    }
    batch_size = max(50, safe_limit * 5)
    cursor_created_at = None
    cursor_id = 0

    while len(selected_events) < safe_limit:
        batch_queryset = selector_queryset
        if cursor_created_at is not None:
            batch_queryset = batch_queryset.filter(
                Q(created_at__gt=cursor_created_at)
                | Q(created_at=cursor_created_at, id__gt=cursor_id)
            )
        batch = list(batch_queryset[:batch_size])
        if not batch:
            break
        for event in batch:
            cursor_created_at = event.created_at
            cursor_id = event.id
            if _should_defer_event(event, now=now):
                result[PROCESS_RESULT_DEFERRED] += 1
                continue
            claim_success = _claim_queue_event(
                queue_queryset,
                event=event,
                statuses=statuses,
                stale_processing_before=stale_processing_before,
            )
            if not claim_success:
                continue
            result[PROCESS_RESULT_SELECTED] += 1
            event.status = IntegrationStatus.PROCESSING
            selected_events.append(event)
            if len(selected_events) >= safe_limit:
                break

    for event in selected_events:
        payload = event.payload or {}
        meta = _queue_meta(payload)
        outcome = _apply_send_result(
            event=event,
            payload=payload,
            meta=meta,
            queue_config=queue_config,
        )
        result[outcome] += 1
        event.payload = payload
        event.save(update_fields=["status", "error_message", "processed_at", "payload"])

    return result
